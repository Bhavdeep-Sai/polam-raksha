import uuid
from collections.abc import Generator
from datetime import timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from app.core.security import hash_secret
from app.db import models as _models  # noqa: F401
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.modules.listings.models import CropCatalog, ListingStatus, ProduceListing
from app.modules.system.models import AuditEvent
from app.modules.users.models import AssistedAccessRelationship, User, UserRole
from app.shared.time import utc_now
from scripts.seed_demo import seed_demo_data


@pytest.fixture
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    """Create a fresh SQLite-backed database using Alembic migrations for each test."""
    db_file = tmp_path / "test_polamraksha.db"
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


def _create_crop(db: Session) -> CropCatalog:
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


def _register_and_login(
    client: TestClient,
    *,
    email: str,
    phone: str,
    password: str,
    role: str,
    pin: str | None = None,
) -> tuple[str, dict[str, str]]:
    reg_payload: dict[str, object] = {
        "full_name": f"Test {role}",
        "role": role,
        "email": email,
        "phone_number": phone,
        "password": password,
        "preferred_language": "te",
    }
    if pin is not None:
        reg_payload["pin"] = pin
    if role == "FARMER":
        reg_payload["village"] = "Tadikonda"
        reg_payload["mandal"] = "Tadikonda"
        reg_payload["district"] = "Guntur"
        reg_payload["exact_pickup_address"] = "Secret Farm Gate 9, Tadikonda"

    reg_res = client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201, reg_res.text

    login_res = client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": password},
    )
    assert login_res.status_code == 200, login_res.text
    token = login_res.json()["access_token"]
    return token, {"Authorization": f"Bearer {token}"}


def test_passwords_and_pins_are_hashed_not_plaintext(
    api_client: TestClient, db_session: Session
) -> None:
    _register_and_login(
        api_client,
        email="farmer1@example.com",
        phone="+919876543210",
        password="StrongPassword!123",
        role="FARMER",
        pin="4829",
    )
    user = db_session.scalar(select(User).where(User.email == "farmer1@example.com"))
    assert user is not None
    assert user.password_hash is not None
    assert user.password_hash != "StrongPassword!123"
    assert user.password_hash.startswith("$argon2")
    assert user.pin_hash is not None
    assert user.pin_hash != "4829"
    assert user.pin_hash.startswith("$argon2")


def test_invalid_login_and_pin_lockout_are_rejected(api_client: TestClient) -> None:
    _register_and_login(
        api_client,
        email="farmer2@example.com",
        phone="+919876543211",
        password="StrongPassword!123",
        role="FARMER",
        pin="5678",
    )

    bad_pw = api_client.post(
        "/api/v1/auth/login",
        json={"identifier": "farmer2@example.com", "password": "WrongPassword"},
    )
    assert bad_pw.status_code == 401
    assert bad_pw.json()["error"]["code"] == "invalid_credentials"

    for _ in range(5):
        bad_pin = api_client.post(
            "/api/v1/auth/pin-login",
            json={"phone_number": "+919876543211", "pin": "0000"},
        )
        assert bad_pin.status_code == 401

    locked = api_client.post(
        "/api/v1/auth/pin-login",
        json={"phone_number": "+919876543211", "pin": "5678"},
    )
    assert locked.status_code == 429
    assert locked.json()["error"]["code"] == "pin_locked"


def test_unauthorized_users_cannot_access_protected_routes(api_client: TestClient) -> None:
    res = api_client.get("/api/v1/auth/me")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "not_authenticated"


def test_buyers_cannot_perform_farmer_actions_and_farmers_isolated(
    api_client: TestClient, db_session: Session
) -> None:
    crop = _create_crop(db_session)
    _, farmer1_hdr = _register_and_login(
        api_client,
        email="f1@example.com",
        phone="+919800000001",
        password="Password!123",
        role="FARMER",
    )
    _, farmer2_hdr = _register_and_login(
        api_client,
        email="f2@example.com",
        phone="+919800000002",
        password="Password!123",
        role="FARMER",
    )
    _, buyer_hdr = _register_and_login(
        api_client,
        email="b1@example.com",
        phone="+919800000003",
        password="Password!123",
        role="BUYER",
    )

    now = utc_now()
    listing_payload = {
        "crop_id": str(crop.id),
        "total_quantity_grams": 100_000,
        "floor_price_paise_per_kg": 2000,
        "harvested_at": (now - timedelta(hours=1)).isoformat(),
        "spoilage_deadline_at": (now + timedelta(hours=24)).isoformat(),
        "approx_location_label": "Tadikonda, Guntur",
        "exact_pickup_address": "Private Plot 99, Tadikonda",
    }

    buyer_create = api_client.post("/api/v1/listings", json=listing_payload, headers=buyer_hdr)
    assert buyer_create.status_code == 403

    farmer_create = api_client.post("/api/v1/listings", json=listing_payload, headers=farmer1_hdr)
    assert farmer_create.status_code == 201
    listing_id = farmer_create.json()["id"]

    # Public listings must not leak exact_pickup_address
    public_res = api_client.get("/api/v1/listings")
    assert public_res.status_code == 200
    assert "exact_pickup_address" not in public_res.json()[0]

    # Farmer 2 cannot modify Farmer 1's listing
    other_patch = api_client.patch(
        f"/api/v1/listings/{listing_id}",
        json={"floor_price_paise_per_kg": 1500},
        headers=farmer2_hdr,
    )
    assert other_patch.status_code == 403


def test_operator_assisted_access_and_admin_impersonation_blocked(
    api_client: TestClient, db_session: Session
) -> None:
    crop = _create_crop(db_session)
    _register_and_login(
        api_client,
        email="farmer_target@example.com",
        phone="+919811111111",
        password="Password!123",
        role="FARMER",
    )
    farmer = db_session.scalar(select(User).where(User.email == "farmer_target@example.com"))
    assert farmer is not None

    operator = User(
        email="op1@example.com",
        phone_number="+919822222222",
        full_name="Operator One",
        role=UserRole.OPERATOR,
        password_hash=hash_secret("OperatorPass!123"),
    )
    admin = User(
        email="admin1@example.com",
        phone_number="+919833333333",
        full_name="Admin One",
        role=UserRole.ADMIN,
        password_hash=hash_secret("AdminPass!123"),
    )
    db_session.add_all([operator, admin])
    db_session.commit()

    op_token = api_client.post(
        "/api/v1/auth/login",
        json={"identifier": "op1@example.com", "password": "OperatorPass!123"},
    ).json()["access_token"]
    op_hdr = {"Authorization": f"Bearer {op_token}"}

    admin_token = api_client.post(
        "/api/v1/auth/login",
        json={"identifier": "admin1@example.com", "password": "AdminPass!123"},
    ).json()["access_token"]
    admin_hdr = {"Authorization": f"Bearer {admin_token}"}

    # Unassigned operator is blocked
    unassigned_res = api_client.get(f"/api/v1/farmers/{farmer.id}/profile", headers=op_hdr)
    assert unassigned_res.status_code == 403
    assert unassigned_res.json()["error"]["code"] == "operator_not_assigned"

    # Admin cannot silently impersonate farmer
    now = utc_now()
    admin_create = api_client.post(
        "/api/v1/listings",
        json={
            "farmer_id": str(farmer.id),
            "crop_id": str(crop.id),
            "total_quantity_grams": 50_000,
            "floor_price_paise_per_kg": 1800,
            "harvested_at": (now - timedelta(hours=1)).isoformat(),
            "spoilage_deadline_at": (now + timedelta(hours=24)).isoformat(),
            "approx_location_label": "Tadikonda",
            "exact_pickup_address": "Plot 1",
        },
        headers=admin_hdr,
    )
    assert admin_create.status_code == 403

    # Assign operator explicitly
    db_session.add(
        AssistedAccessRelationship(
            operator_id=operator.id,
            farmer_id=farmer.id,
            is_active=True,
        )
    )
    db_session.commit()

    assigned_res = api_client.get(f"/api/v1/farmers/{farmer.id}/profile", headers=op_hdr)
    assert assigned_res.status_code == 200
    assert assigned_res.json()["exact_pickup_address"] == "Secret Farm Gate 9, Tadikonda"

    audit = db_session.scalar(
        select(AuditEvent).where(
            AuditEvent.actor_user_id == operator.id,
            AuditEvent.acting_as_farmer_id == farmer.id,
            AuditEvent.action == "OPERATOR_VIEWED_FARMER_PROFILE",
        )
    )
    assert audit is not None


def test_refresh_token_rotation_csrf_and_logout(api_client: TestClient) -> None:
    _register_and_login(
        api_client,
        email="rotator@example.com",
        phone="+919844444444",
        password="Password!123",
        role="BUYER",
    )

    # Cookie-based refresh without CSRF header must fail
    no_csrf = api_client.post("/api/v1/auth/refresh")
    assert no_csrf.status_code == 403
    assert no_csrf.json()["error"]["code"] == "csrf_validation_failed"

    csrf_token = api_client.cookies.get("polam_csrf_token")
    first_refresh = api_client.cookies.get("polam_refresh_token")
    assert csrf_token and first_refresh

    rotated = api_client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert rotated.status_code == 200
    second_refresh = api_client.cookies.get("polam_refresh_token")
    second_csrf = api_client.cookies.get("polam_csrf_token")
    assert second_refresh and second_refresh != first_refresh

    # Reusing the old refresh token triggers family revocation
    api_client.cookies.clear()
    reuse = api_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first_refresh},
    )
    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] == "refresh_token_reused"

    # Second token in the same family is now revoked too
    assert second_csrf and second_refresh
    blocked = api_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": second_refresh},
    )
    assert blocked.status_code == 401

    # Fresh login + logout revokes token
    api_client.post(
        "/api/v1/auth/login",
        json={"identifier": "rotator@example.com", "password": "Password!123"},
    )
    logout_csrf = api_client.cookies.get("polam_csrf_token") or ""
    logout_res = api_client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": logout_csrf},
    )
    assert logout_res.status_code == 200
    assert logout_res.json()["status"] == "logged_out"


def test_invalid_inventory_values_rejected_by_database(db_session: Session) -> None:
    crop = _create_crop(db_session)
    farmer = User(
        email="inv@example.com",
        phone_number="+919855555555",
        full_name="Inventory Farmer",
        role=UserRole.FARMER,
        password_hash=hash_secret("Password!123"),
    )
    db_session.add(farmer)
    db_session.commit()

    now = utc_now()
    # available + reserved + collected > total must fail DB CheckConstraint
    bad_listing = ProduceListing(
        farmer_id=farmer.id,
        created_by_user_id=farmer.id,
        crop_id=crop.id,
        status=ListingStatus.ACTIVE,
        total_quantity_grams=1000,
        available_quantity_grams=800,
        reserved_quantity_grams=300,
        collected_quantity_grams=0,
        floor_price_paise_per_kg=1000,
        harvested_at=now,
        spoilage_deadline_at=now + timedelta(hours=10),
        approx_location_label="Guntur",
        exact_pickup_address="Plot 1",
    )
    db_session.add(bad_listing)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Negative available quantity must fail DB CheckConstraint
    neg_listing = ProduceListing(
        farmer_id=farmer.id,
        created_by_user_id=farmer.id,
        crop_id=crop.id,
        status=ListingStatus.ACTIVE,
        total_quantity_grams=1000,
        available_quantity_grams=-10,
        reserved_quantity_grams=0,
        collected_quantity_grams=0,
        floor_price_paise_per_kg=1000,
        harvested_at=now,
        spoilage_deadline_at=now + timedelta(hours=10),
        approx_location_label="Guntur",
        exact_pickup_address="Plot 1",
    )
    db_session.add(neg_listing)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_demo_seeder_populates_simulated_data(db_session: Session) -> None:
    seed_demo_data(db_session)
    crops = db_session.scalars(select(CropCatalog)).all()
    assert len(crops) == 5
    simulated_listings = db_session.scalars(
        select(ProduceListing).where(ProduceListing.is_simulated.is_(True))
    ).all()
    assert len(simulated_listings) == 1
    assert uuid.UUID(str(simulated_listings[0].id))
    assert len(Base.metadata.tables) >= 20
