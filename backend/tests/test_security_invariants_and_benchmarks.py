import time
from collections.abc import Generator
from datetime import timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from app.core.security import hash_secret
from app.db import models as _models  # noqa: F401
from app.db.session import get_db
from app.main import app
from app.modules.allocation.solver import (
    AllocationInput,
    AllocationStrategy,
    BuyerOfferInput,
    SolverStatus,
    solve_allocation,
)
from app.modules.ivr.voice_adapter import extract_listing_fields_from_transcript
from app.modules.listings.models import CropCatalog, ListingStatus, ProduceListing
from app.modules.users.models import FarmerProfile, User, UserRole
from app.shared.time import utc_now


@pytest.fixture
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    db_file = tmp_path / "test_security_bench.db"
    db_url = f"sqlite:///{db_file}"

    alembic_cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    testing_session_local = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def api_client(db_session: Session) -> Generator[TestClient, None, None]:
    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_unsafe_photo_url_schemes_rejected(api_client: TestClient, db_session: Session) -> None:
    crop = CropCatalog(code="TOMATO", name_en="Tomato", name_te="టమాటా", default_shelf_life_hours=48)
    farmer = User(
        email="xss_f@example.com",
        phone_number="+919500000001",
        full_name="XSS Test Farmer",
        role=UserRole.FARMER,
        password_hash=hash_secret("Password!123"),
    )
    db_session.add_all([crop, farmer])
    db_session.flush()
    db_session.add(
        FarmerProfile(
            user_id=farmer.id,
            village="Tenali",
            mandal="Tenali",
            district="Guntur",
            exact_pickup_address="Gate 1",
        )
    )
    db_session.commit()

    token = api_client.post(
        "/api/v1/auth/login",
        json={"identifier": "xss_f@example.com", "password": "Password!123"},
    ).json()["access_token"]

    resp = api_client.post(
        "/api/v1/listings",
        json={
            "crop_id": str(crop.id),
            "quantity_value": 50,
            "quantity_unit": "KG",
            "floor_price_paise_per_kg": 2000,
            "harvested_at": (utc_now() - timedelta(hours=1)).isoformat(),
            "urgency_option": "WITHIN_12H",
            "quality_grade": "GRADE_A",
            "photo_urls": ["javascript:alert(1)"],
            "transport_responsibility": "BUYER_PICKUP",
            "auto_allocate_approved": False,
            "approx_location_label": "Tenali, Guntur",
            "exact_pickup_address": "Plot 12",
            "consent_confirmed": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_failure_modes_speech_unavailable_and_no_eligible_buyers() -> None:
    # Deterministic transcript extraction works without external speech/AI provider
    speech_res = extract_listing_fields_from_transcript("50 kg tomato")
    assert speech_res.available is True
    assert speech_res.crop_code == "TOMATO"
    assert speech_res.quantity_kg == 50.0

    # Solver with no eligible buyers returns INFEASIBLE without crashing
    now = utc_now()
    solve_res = solve_allocation(
        AllocationInput(
            available_quantity_grams=100_000,
            committed_quantity_grams=0,
            reserve_price_paise_per_kg=2000,
            hard_collection_deadline=now + timedelta(hours=12),
            strategy=AllocationStrategy.REVENUE_FIRST,
            offers=[],
        )
    )
    assert solve_res.solver_status == SolverStatus.INFEASIBLE
    assert solve_res.selected_buyers == []


def test_realistic_workload_benchmarks_and_query_counts(
    api_client: TestClient, db_session: Session
) -> None:
    now = utc_now()
    crop = CropCatalog(code="TOMATO", name_en="Tomato", name_te="టమాటా", default_shelf_life_hours=48)
    admin = User(
        email="bench_adm@example.com",
        phone_number="+919500000010",
        full_name="Bench Admin",
        role=UserRole.ADMIN,
        password_hash=hash_secret("Password!123"),
    )
    farmer = User(
        email="bench_frm@example.com",
        phone_number="+919500000011",
        full_name="Bench Farmer",
        role=UserRole.FARMER,
        password_hash=hash_secret("Password!123"),
    )
    db_session.add_all([crop, admin, farmer])
    db_session.flush()

    for i in range(25):
        db_session.add(
            ProduceListing(
                farmer_id=farmer.id,
                created_by_user_id=farmer.id,
                crop_id=crop.id,
                status=ListingStatus.ACTIVE,
                total_quantity_grams=100_000,
                available_quantity_grams=100_000,
                reserved_quantity_grams=0,
                collected_quantity_grams=0,
                floor_price_paise_per_kg=2000 + i * 10,
                harvested_at=now - timedelta(hours=1),
                spoilage_deadline_at=now + timedelta(hours=24),
                approx_location_label=f"Village {i}, Guntur",
                exact_pickup_address=f"Plot {i}",
            )
        )
    db_session.commit()

    query_count = 0

    def _count_queries(*_args: object) -> None:
        nonlocal query_count
        query_count += 1

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", _count_queries)

    t0 = time.perf_counter()
    listings_resp = api_client.get("/api/v1/listings")
    listings_ms = (time.perf_counter() - t0) * 1000.0
    listings_queries = query_count
    assert listings_resp.status_code == 200
    assert len(listings_resp.json()) == 25

    admin_token = api_client.post(
        "/api/v1/auth/login",
        json={"identifier": "bench_adm@example.com", "password": "Password!123"},
    ).json()["access_token"]

    query_count = 0
    t1 = time.perf_counter()
    analytics_resp = api_client.get(
        "/api/v1/analytics/impact",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    analytics_ms = (time.perf_counter() - t1) * 1000.0
    analytics_queries = query_count
    assert analytics_resp.status_code == 200

    event.remove(engine, "before_cursor_execute", _count_queries)

    # Solver benchmark with 20 offers
    offers = [
        BuyerOfferInput(
            buyer_id=f"buyer-{i}",
            unit_price_paise_per_kg=2100 + i * 25,
            min_quantity_grams=5_000,
            max_quantity_grams=25_000,
            estimated_collection_at=now + timedelta(hours=4),
            farmer_paid_variable_transport_paise_per_kg=0,
            farmer_paid_fixed_pickup_cost_paise=0,
            reliability_score=95,
        )
        for i in range(20)
    ]
    t2 = time.perf_counter()
    solve_res = solve_allocation(
        AllocationInput(
            available_quantity_grams=200_000,
            committed_quantity_grams=0,
            reserve_price_paise_per_kg=2000,
            hard_collection_deadline=now + timedelta(hours=12),
            strategy=AllocationStrategy.REVENUE_FIRST,
            offers=offers,
        )
    )
    solver_ms = (time.perf_counter() - t2) * 1000.0
    assert solve_res.solver_status in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}

    print(
        f"\nBENCHMARK_RESULTS: listings_ms={listings_ms:.2f} listings_queries={listings_queries} "
        f"analytics_ms={analytics_ms:.2f} analytics_queries={analytics_queries} "
        f"solver_20_offers_ms={solver_ms:.2f}"
    )
