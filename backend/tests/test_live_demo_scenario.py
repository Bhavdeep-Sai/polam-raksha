from collections.abc import Generator
from datetime import timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from app.core.config import Settings, get_settings
from app.core.security import hash_secret
from app.db import models as _models  # noqa: F401
from app.db.session import get_db
from app.main import app
from app.modules.listings.models import CropCatalog, ListingStatus, ProduceListing
from app.modules.users.models import User, UserRole
from app.shared.time import utc_now


@pytest.fixture
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    db_file = tmp_path / "test_live_demo.db"
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
def demo_client(db_session: Session) -> Generator[TestClient, None, None]:
    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    def _override_settings() -> Settings:
        return Settings(app_env="test", demo_mode_enabled=True, demo_auction_duration_seconds=60)

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = _override_settings
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_complete_live_demo_scenario_and_production_isolation(
    demo_client: TestClient, db_session: Session
) -> None:
    now = utc_now()
    crop = CropCatalog(code="TOMATO", name_en="Tomato", name_te="టమాటా", default_shelf_life_hours=48)
    admin = User(
        email="demo.admin@polamraksha.local",
        phone_number="+919000000099",
        full_name="Demo Admin",
        role=UserRole.ADMIN,
        password_hash=hash_secret("DemoAdmin#2026"),
    )
    prod_farmer = User(
        email="real.farmer@example.com",
        phone_number="+919600000001",
        full_name="Real Farmer",
        role=UserRole.FARMER,
        password_hash=hash_secret("Password!123"),
    )
    db_session.add_all([crop, admin, prod_farmer])
    db_session.flush()

    # Create 1 real non-simulated listing to verify demo reset NEVER touches production data
    real_listing = ProduceListing(
        farmer_id=prod_farmer.id,
        created_by_user_id=prod_farmer.id,
        crop_id=crop.id,
        status=ListingStatus.ACTIVE,
        total_quantity_grams=50_000,
        available_quantity_grams=50_000,
        reserved_quantity_grams=0,
        collected_quantity_grams=0,
        floor_price_paise_per_kg=2500,
        harvested_at=now - timedelta(hours=1),
        spoilage_deadline_at=now + timedelta(hours=24),
        approx_location_label="Real Village",
        exact_pickup_address="Real Gate",
        is_simulated=False,
    )
    db_session.add(real_listing)
    db_session.commit()

    admin_token = demo_client.post(
        "/api/v1/auth/login",
        json={"identifier": "demo.admin@polamraksha.local", "password": "DemoAdmin#2026"},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Start 300 kg Tomato scenario
    start_resp = demo_client.post("/api/v1/admin/demo/scenario/start", headers=headers)
    assert start_resp.status_code == 200
    auction_id = start_resp.json()["auction_id"]
    assert start_resp.json()["quantity_grams"] == 300_000

    # 2. Simulate 3+ competitive buyer bids & increase
    bids_resp = demo_client.post(
        "/api/v1/admin/demo/scenario/simulate-bids",
        json={"auction_id": auction_id},
        headers=headers,
    )
    assert bids_resp.status_code == 200
    assert bids_resp.json()["bids_placed"] == 4

    # 3. Close auction & run CP-SAT allocation
    alloc_resp = demo_client.post(
        "/api/v1/admin/demo/scenario/advance-allocate",
        json={"auction_id": auction_id},
        headers=headers,
    )
    assert alloc_resp.status_code == 200
    assert alloc_resp.json()["solver_status"] in {"OPTIMAL", "FEASIBLE"}
    assert alloc_resp.json()["orders_created"] >= 1

    # 4. Simulate buyer cancellation & standby recovery
    cancel_resp = demo_client.post(
        "/api/v1/admin/demo/scenario/simulate-cancellation",
        json={"auction_id": auction_id},
        headers=headers,
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["released_grams"] > 0
    assert cancel_resp.json()["recovered_orders"] >= 1

    # 5. Record simulated collection
    collect_resp = demo_client.post(
        "/api/v1/admin/demo/scenario/record-collection",
        json={"auction_id": auction_id},
        headers=headers,
    )
    assert collect_resp.status_code == 200
    assert collect_resp.json()["collected_grams"] > 0

    # 6. Verify analytics updated for demo, production untouched
    analytics = demo_client.get(
        "/api/v1/analytics/impact?include_simulated=true",
        headers=headers,
    ).json()
    assert analytics["production"]["produce_listed_grams"] == 50_000
    assert analytics["production"]["produce_collected_grams"] == 0
    assert analytics["demo_simulated"]["produce_listed_grams"] == 300_000
    assert analytics["demo_simulated"]["produce_collected_grams"] > 0

    # 7. Reset demo data only -> real listing preserved
    reset_resp = demo_client.post("/api/v1/admin/demo/scenario/reset", headers=headers)
    assert reset_resp.status_code == 200
    assert reset_resp.json()["cleared_simulated_listings"] == 1
    remaining_real = db_session.scalar(
        select(ProduceListing).where(ProduceListing.id == real_listing.id)
    )
    assert remaining_real is not None

