import uuid
from collections.abc import Generator
from datetime import timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from app.core.security import hash_secret
from app.db import models as _models  # noqa: F401
from app.db.session import get_db
from app.main import app
from app.modules.auctions.models import Auction, AuctionStatus
from app.modules.listings.models import CropCatalog, ListingStatus, ProduceListing
from app.modules.system.models import AuditEvent
from app.modules.users.models import User, UserRole
from app.shared.time import utc_now


@pytest.fixture
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    db_file = tmp_path / "test_phase4.db"
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


def _seed_crop(db: Session) -> CropCatalog:
    crop = CropCatalog(
        code="TOMATO",
        name_en="Tomato",
        name_te="టమాటా",
        default_shelf_life_hours=48,
    )
    db.add(crop)
    db.commit()
    db.refresh(crop)
    return crop


def _login_user(
    client: TestClient,
    db: Session,
    *,
    email: str,
    phone: str,
    role: UserRole,
) -> tuple[User, dict[str, str]]:
    user = User(
        email=email,
        phone_number=phone,
        full_name=f"User {role.value}",
        preferred_language="te",
        role=role,
        password_hash=hash_secret("Password!123"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    res = client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": "Password!123"},
    )
    assert res.status_code == 200
    token = res.json()["access_token"]
    return user, {"Authorization": f"Bearer {token}"}


def test_valid_listings_create_auctions_with_feasible_deadlines(
    api_client: TestClient, db_session: Session
) -> None:
    crop = _seed_crop(db_session)
    _, farmer_hdr = _login_user(
        api_client,
        db_session,
        email="f_sched@example.com",
        phone="+919700000001",
        role=UserRole.FARMER,
    )

    # Normal 12h urgency -> auction mode
    res_12h = api_client.post(
        "/api/v1/listings",
        json={
            "crop_id": str(crop.id),
            "quantity_value": 2,
            "quantity_unit": "QUINTAL",
            "floor_price_paise_per_kg": 2200,
            "harvested_at": (utc_now() - timedelta(hours=1)).isoformat(),
            "urgency_option": "WITHIN_12H",
            "quality_grade": "GRADE_A",
            "transport_responsibility": "BUYER_PICKUP",
            "approx_location_label": "Tadikonda, Guntur",
            "exact_pickup_address": "Plot 7, Tadikonda",
        },
        headers=farmer_hdr,
    )
    assert res_12h.status_code == 201, res_12h.text
    data = res_12h.json()
    assert data["total_quantity_grams"] == 200_000
    assert data["is_direct_offer_mode"] is False
    assert data["auction_status"] == AuctionStatus.OPEN.value
    assert data["bidding_hard_close_at"] < data["spoilage_deadline_at"]

    auction = db_session.scalar(
        select(Auction).where(Auction.listing_id == uuid.UUID(data["id"]))
    )
    assert auction is not None

    # Urgent 2h -> direct-offer mode enabled
    res_2h = api_client.post(
        "/api/v1/listings",
        json={
            "crop_id": str(crop.id),
            "quantity_value": 50,
            "quantity_unit": "KG",
            "floor_price_paise_per_kg": 1800,
            "harvested_at": (utc_now() - timedelta(hours=1)).isoformat(),
            "urgency_option": "WITHIN_2H",
            "approx_location_label": "Tenali, Guntur",
            "exact_pickup_address": "Plot 9, Tenali",
        },
        headers=farmer_hdr,
    )
    assert res_2h.status_code == 201
    assert res_2h.json()["is_direct_offer_mode"] is True


def test_invalid_quantities_prices_and_expired_deadlines_rejected(
    api_client: TestClient, db_session: Session
) -> None:
    crop = _seed_crop(db_session)
    _, farmer_hdr = _login_user(
        api_client,
        db_session,
        email="f_invalid@example.com",
        phone="+919700000002",
        role=UserRole.FARMER,
    )

    now = utc_now()

    bad_qty = api_client.post(
        "/api/v1/listings",
        json={
            "crop_id": str(crop.id),
            "quantity_value": 0,
            "quantity_unit": "KG",
            "floor_price_paise_per_kg": 2000,
            "harvested_at": now.isoformat(),
            "urgency_option": "WITHIN_12H",
            "approx_location_label": "Guntur",
            "exact_pickup_address": "Plot 1",
        },
        headers=farmer_hdr,
    )
    assert bad_qty.status_code == 422

    bad_price = api_client.post(
        "/api/v1/listings",
        json={
            "crop_id": str(crop.id),
            "quantity_value": 50,
            "quantity_unit": "KG",
            "floor_price_paise_per_kg": -100,
            "harvested_at": now.isoformat(),
            "urgency_option": "WITHIN_12H",
            "approx_location_label": "Guntur",
            "exact_pickup_address": "Plot 1",
        },
        headers=farmer_hdr,
    )
    assert bad_price.status_code == 422

    expired_deadline = api_client.post(
        "/api/v1/listings",
        json={
            "crop_id": str(crop.id),
            "quantity_value": 50,
            "quantity_unit": "KG",
            "floor_price_paise_per_kg": 2000,
            "harvested_at": (now - timedelta(hours=3)).isoformat(),
            "urgency_option": "CUSTOM",
            "spoilage_deadline_at": (now - timedelta(minutes=10)).isoformat(),
            "approx_location_label": "Guntur",
            "exact_pickup_address": "Plot 1",
        },
        headers=farmer_hdr,
    )
    assert expired_deadline.status_code == 422
    assert expired_deadline.json()["error"]["code"] == "expired_collection_deadline"

    infeasible = api_client.post(
        "/api/v1/listings",
        json={
            "crop_id": str(crop.id),
            "quantity_value": 50,
            "quantity_unit": "KG",
            "floor_price_paise_per_kg": 2000,
            "harvested_at": (now - timedelta(hours=1)).isoformat(),
            "urgency_option": "CUSTOM",
            "spoilage_deadline_at": (now + timedelta(minutes=20)).isoformat(),
            "approx_location_label": "Guntur",
            "exact_pickup_address": "Plot 1",
        },
        headers=farmer_hdr,
    )
    assert infeasible.status_code == 422
    assert infeasible.json()["error"]["code"] == "infeasible_deadline_schedule"


def test_assisted_registration_records_consent_and_rejects_unauthorized_operator(
    api_client: TestClient, db_session: Session
) -> None:
    crop = _seed_crop(db_session)
    operator_1, op1_hdr = _login_user(
        api_client,
        db_session,
        email="op_a@example.com",
        phone="+919700000003",
        role=UserRole.OPERATOR,
    )
    _, op2_hdr = _login_user(
        api_client,
        db_session,
        email="op_b@example.com",
        phone="+919700000004",
        role=UserRole.OPERATOR,
    )

    # Missing consent must be rejected
    no_consent = api_client.post(
        "/api/v1/farmers/assisted",
        json={
            "full_name": "సుబ్బారావు",
            "preferred_language": "te",
            "village": "Pedakakani",
            "district": "Guntur",
            "consent_method": "IN_PERSON_VERBAL",
            "consent_confirmed": False,
        },
        headers=op1_hdr,
    )
    assert no_consent.status_code == 422
    assert no_consent.json()["error"]["code"] == "farmer_consent_required"

    # Valid assisted onboarding without phone/Aadhaar/bank
    onboard_res = api_client.post(
        "/api/v1/farmers/assisted",
        json={
            "full_name": "సుబ్బారావు",
            "preferred_language": "te",
            "village": "Pedakakani",
            "district": "Guntur",
            "consent_method": "IN_PERSON_VERBAL",
            "consent_confirmed": True,
        },
        headers=op1_hdr,
    )
    assert onboard_res.status_code == 201, onboard_res.text
    farmer_id = onboard_res.json()["farmer_id"]

    # Operator 2 (unassigned) cannot create a listing for this farmer
    unauth_list = api_client.post(
        "/api/v1/listings",
        json={
            "farmer_id": farmer_id,
            "crop_id": str(crop.id),
            "quantity_value": 40,
            "quantity_unit": "KG",
            "floor_price_paise_per_kg": 1900,
            "harvested_at": (utc_now() - timedelta(hours=1)).isoformat(),
            "urgency_option": "WITHIN_6H",
            "approx_location_label": "Pedakakani, Guntur",
            "exact_pickup_address": "Pedakakani Center",
            "consent_confirmed": True,
        },
        headers=op2_hdr,
    )
    assert unauth_list.status_code == 403
    assert unauth_list.json()["error"]["code"] == "operator_not_assigned"

    # Assigned Operator 1 creates listing via the same service and records audit
    auth_list = api_client.post(
        "/api/v1/listings",
        json={
            "farmer_id": farmer_id,
            "crop_id": str(crop.id),
            "quantity_value": 40,
            "quantity_unit": "KG",
            "floor_price_paise_per_kg": 1900,
            "harvested_at": (utc_now() - timedelta(hours=1)).isoformat(),
            "urgency_option": "WITHIN_6H",
            "approx_location_label": "Pedakakani, Guntur",
            "exact_pickup_address": "Pedakakani Center",
            "consent_confirmed": True,
        },
        headers=op1_hdr,
    )
    assert auth_list.status_code == 201
    audit = db_session.scalar(
        select(AuditEvent).where(
            AuditEvent.actor_user_id == operator_1.id,
            AuditEvent.action == "LISTING_CREATED",
        )
    )
    assert audit is not None
    assert str(audit.acting_as_farmer_id) == farmer_id


def test_committed_inventory_cannot_be_silently_changed(
    api_client: TestClient, db_session: Session
) -> None:
    crop = _seed_crop(db_session)
    _, farmer_hdr = _login_user(
        api_client,
        db_session,
        email="f_commit@example.com",
        phone="+919700000005",
        role=UserRole.FARMER,
    )

    create_res = api_client.post(
        "/api/v1/listings",
        json={
            "crop_id": str(crop.id),
            "quantity_value": 100,
            "quantity_unit": "KG",
            "floor_price_paise_per_kg": 2000,
            "harvested_at": (utc_now() - timedelta(hours=1)).isoformat(),
            "urgency_option": "WITHIN_24H",
            "approx_location_label": "Guntur",
            "exact_pickup_address": "Plot 5",
        },
        headers=farmer_hdr,
    )
    assert create_res.status_code == 201
    listing_id = create_res.json()["id"]

    # Simulate 40 kg committed/reserved
    listing = db_session.scalar(
        select(ProduceListing).where(ProduceListing.id == uuid.UUID(listing_id))
    )
    assert listing is not None
    listing.available_quantity_grams = 60_000
    listing.reserved_quantity_grams = 40_000
    listing.status = ListingStatus.PARTIALLY_ALLOCATED
    db_session.commit()

    # Farmer cannot silently change agreed floor price or cancel entire listing
    price_change = api_client.patch(
        f"/api/v1/listings/{listing_id}",
        json={"floor_price_paise_per_kg": 2500},
        headers=farmer_hdr,
    )
    assert price_change.status_code == 409
    assert price_change.json()["error"]["code"] == "committed_inventory_locked"

    # Farmer CAN cancel uncommitted 60 kg while preserving 40 kg committed
    cancel_uncommitted = api_client.post(
        f"/api/v1/listings/{listing_id}/cancel-uncommitted",
        headers=farmer_hdr,
    )
    assert cancel_uncommitted.status_code == 200
    body = cancel_uncommitted.json()
    assert body["available_quantity_grams"] == 0
    assert body["reserved_quantity_grams"] == 40_000
    assert body["total_quantity_grams"] == 40_000
    assert body["status"] == ListingStatus.FULLY_ALLOCATED.value
