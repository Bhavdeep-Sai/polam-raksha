import hashlib
import hmac
import json
from collections.abc import Generator
from datetime import timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from app.core.config import get_settings
from app.core.security import hash_secret
from app.db import models as _models  # noqa: F401
from app.db.session import get_db
from app.main import app
from app.modules.allocation.models import Allocation, AllocationRun, AllocationRunStatus
from app.modules.auctions.models import Auction, AuctionStatus
from app.modules.ivr.prompts import compose_number_tokens
from app.modules.ivr.voice_adapter import (
    extract_listing_fields_from_transcript,
    transcribe_audio_with_optional_whisper,
)
from app.modules.listings.models import CropCatalog, ListingStatus, ProduceListing
from app.modules.orders.models import Order
from app.modules.users.models import FarmerProfile, User, UserRole
from app.shared.time import utc_now


@pytest.fixture
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    db_file = tmp_path / "test_phase7.db"
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


def _seed_farmer_and_crop(db: Session, *, phone: str = "+919400000001") -> tuple[User, CropCatalog]:
    crop = CropCatalog(
        code="TOMATO",
        name_en="Tomato",
        name_te="టమాటా",
        default_shelf_life_hours=48,
    )
    farmer = User(
        email="ivr_farmer@example.com",
        phone_number=phone,
        full_name="రామయ్య",
        preferred_language="te",
        role=UserRole.FARMER,
        password_hash=hash_secret("Pass!123"),
        pin_hash=hash_secret("4321"),
    )
    db.add_all([crop, farmer])
    db.flush()
    db.add(
        FarmerProfile(
            user_id=farmer.id,
            village="Tadikonda",
            mandal="Tadikonda",
            district="Guntur",
            exact_pickup_address="Plot 12, Tadikonda",
        )
    )
    db.commit()
    return farmer, crop


def test_complete_keypad_listing_registration_and_corrections(
    api_client: TestClient, db_session: Session
) -> None:
    farmer, _ = _seed_farmer_and_crop(db_session)

    start = api_client.post(
        "/api/v1/ivr/sessions",
        json={
            "caller_phone": farmer.phone_number,
            "language": "te",
            "provider": "BROWSER_SIMULATOR",
            "external_call_id": "call-reg-1",
        },
    )
    assert start.status_code == 201
    sid = start.json()["session_id"]
    assert start.json()["session_state"] == "AUTH_PIN"

    # Authenticate with PIN
    r = api_client.post(f"/api/v1/ivr/sessions/{sid}/dtmf", json={"digits": "4321#"})
    assert r.status_code == 200
    assert r.json()["session_state"] == "MAIN_MENU"
    assert "పంట అమ్మడానికి 1" in r.json()["prompt"]["transcript"]

    # Choose 1 (Sell produce)
    r = api_client.post(f"/api/v1/ivr/sessions/{sid}/dtmf", json={"digits": "1"})
    assert r.json()["session_state"] == "SELL_SELECT_CROP"

    # Invalid crop 9 -> handled gracefully
    bad_crop = api_client.post(f"/api/v1/ivr/sessions/{sid}/dtmf", json={"digits": "9"})
    assert bad_crop.json()["session_state"] == "SELL_SELECT_CROP"
    assert bad_crop.json()["retry_count"] == 1

    # Valid crop 1
    r = api_client.post(f"/api/v1/ivr/sessions/{sid}/dtmf", json={"digits": "1"})
    assert r.json()["session_state"] == "SELL_ENTER_QUANTITY"

    # Enter quantity 50#, then price 20#, then * to correct quantity to 75#
    r = api_client.post(f"/api/v1/ivr/sessions/{sid}/dtmf", json={"digits": "50#"})
    assert r.json()["session_state"] == "SELL_ENTER_PRICE"
    r = api_client.post(f"/api/v1/ivr/sessions/{sid}/dtmf", json={"digits": "*"})
    assert r.json()["session_state"] == "SELL_ENTER_QUANTITY"

    # Interrupted call resumes cleanly at SELL_ENTER_QUANTITY
    resumed = api_client.post(
        "/api/v1/ivr/sessions",
        json={
            "caller_phone": farmer.phone_number,
            "language": "te",
            "external_call_id": "call-reg-1",
        },
    )
    assert resumed.json()["session_id"] == sid
    assert resumed.json()["session_state"] == "SELL_ENTER_QUANTITY"

    r = api_client.post(f"/api/v1/ivr/sessions/{sid}/dtmf", json={"digits": "75#"})
    assert r.json()["session_state"] == "SELL_ENTER_PRICE"
    r = api_client.post(f"/api/v1/ivr/sessions/{sid}/dtmf", json={"digits": "25#"})
    assert r.json()["session_state"] == "SELL_SELECT_URGENCY"
    r = api_client.post(f"/api/v1/ivr/sessions/{sid}/dtmf", json={"digits": "3"})
    assert r.json()["session_state"] == "SELL_CONFIRM"
    assert "75" in r.json()["prompt"]["transcript"]

    # Confirm with duplicate webhook_id -> creates exactly 1 listing
    confirm = api_client.post(
        f"/api/v1/ivr/sessions/{sid}/dtmf",
        json={"digits": "1", "webhook_id": "wh-confirm-1"},
    )
    assert confirm.status_code == 200
    assert confirm.json()["prompt"]["prompt_key"] == "SELL_CREATED"

    dup = api_client.post(
        f"/api/v1/ivr/sessions/{sid}/dtmf",
        json={"digits": "1", "webhook_id": "wh-confirm-1"},
    )
    assert dup.status_code == 200

    listings = db_session.scalars(
        select(ProduceListing).where(ProduceListing.farmer_id == farmer.id)
    ).all()
    assert len(listings) == 1
    assert listings[0].total_quantity_grams == 75_000
    assert listings[0].floor_price_paise_per_kg == 2500


def test_ivr_offer_approval_uses_existing_order_services(
    api_client: TestClient, db_session: Session
) -> None:
    farmer, crop = _seed_farmer_and_crop(db_session, phone="+919400000002")
    buyer = User(
        email="ivr_buyer@example.com",
        phone_number="+919400000099",
        full_name="Buyer",
        role=UserRole.BUYER,
        password_hash=hash_secret("Pass!123"),
    )
    db_session.add(buyer)
    db_session.flush()

    now = utc_now()
    listing = ProduceListing(
        farmer_id=farmer.id,
        created_by_user_id=farmer.id,
        crop_id=crop.id,
        status=ListingStatus.ACTIVE,
        total_quantity_grams=100_000,
        available_quantity_grams=100_000,
        reserved_quantity_grams=0,
        collected_quantity_grams=0,
        floor_price_paise_per_kg=2000,
        harvested_at=now - timedelta(hours=1),
        spoilage_deadline_at=now + timedelta(hours=10),
        approx_location_label="Guntur",
        exact_pickup_address="Plot 12",
    )
    db_session.add(listing)
    db_session.flush()

    auction = Auction(
        listing_id=listing.id,
        status=AuctionStatus.CLOSED,
        min_bid_paise_per_kg=2000,
        starts_at=now - timedelta(hours=2),
        ends_at=now - timedelta(minutes=5),
        hard_close_at=now + timedelta(hours=1),
    )
    db_session.add(auction)
    db_session.flush()

    run = AllocationRun(
        auction_id=auction.id,
        status=AllocationRunStatus.SOLVED,
        solver_status="OPTIMAL",
        gross_revenue_paise=220_000,
        transportation_cost_paise=10_000,
        estimated_net_revenue_paise=210_000,
        unallocated_quantity_grams=0,
        is_approved=False,
    )
    db_session.add(run)
    db_session.flush()

    db_session.add(
        Allocation(
            allocation_run_id=run.id,
            auction_id=auction.id,
            buyer_id=buyer.id,
            allocated_quantity_grams=100_000,
            unit_price_paise_per_kg=2200,
            transport_cost_paise=10_000,
        )
    )
    db_session.commit()

    start = api_client.post(
        "/api/v1/ivr/sessions",
        json={"caller_phone": farmer.phone_number, "language": "en"},
    )
    sid = start.json()["session_id"]
    api_client.post(f"/api/v1/ivr/sessions/{sid}/dtmf", json={"digits": "4321#"})

    # Press 3 for offer approval -> announces summary
    offer = api_client.post(f"/api/v1/ivr/sessions/{sid}/dtmf", json={"digits": "3"})
    assert offer.json()["session_state"] == "OFFER_APPROVAL"
    assert "2100" in offer.json()["prompt"]["transcript"]

    # Press 1 to approve -> creates Order
    approved = api_client.post(f"/api/v1/ivr/sessions/{sid}/dtmf", json={"digits": "1"})
    assert approved.json()["prompt"]["prompt_key"] == "OFFER_APPROVED"
    orders = db_session.scalars(select(Order)).all()
    assert len(orders) == 1


def test_ivr_pin_rate_limit_and_webhook_signature_and_voice_adapter(
    api_client: TestClient, db_session: Session
) -> None:
    farmer, _ = _seed_farmer_and_crop(db_session, phone="+919400000003")

    start = api_client.post(
        "/api/v1/ivr/sessions",
        json={"caller_phone": farmer.phone_number, "language": "te"},
    )
    sid = start.json()["session_id"]

    for _ in range(5):
        bad = api_client.post(f"/api/v1/ivr/sessions/{sid}/dtmf", json={"digits": "0000#"})
        assert bad.status_code == 401

    locked = api_client.post(f"/api/v1/ivr/sessions/{sid}/dtmf", json={"digits": "4321#"})
    assert locked.status_code == 429
    assert locked.json()["error"]["code"] == "pin_locked"

    # Webhook signature check for Asterisk/SIP
    body = json.dumps({
        "channel_id": "ast-1",
        "event_id": "ev-1",
        "caller_number": farmer.phone_number,
        "dtmf_digit": "",
    }).encode("utf-8")
    bad_sig = api_client.post(
        "/api/v1/ivr/webhooks/asterisk_sip",
        content=body,
        headers={"Content-Type": "application/json", "X-Provider-Signature": "bad"},
    )
    assert bad_sig.status_code == 401

    secret = get_settings().ivr_webhook_secret
    good_sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    ok_wh = api_client.post(
        "/api/v1/ivr/webhooks/asterisk_sip",
        content=body,
        headers={"Content-Type": "application/json", "X-Provider-Signature": good_sig},
    )
    assert ok_wh.status_code == 200
    assert ok_wh.json()["asterisk_action"] == "PLAY_AND_GATHER"

    # Number audio composition & optional Whisper adapter
    assert compose_number_tokens(250, "te") == ["2", "100", "50"]
    extracted = extract_listing_fields_from_transcript("టమాటా 50 కిలోలు 25 రూపాయలు 6 గంటల్లో")
    assert extracted.crop_code == "TOMATO"
    assert extracted.quantity_kg == 50.0
    assert extracted.price_inr_per_kg == 25
    assert extracted.urgency_option == "WITHIN_6H"

    whisper_res = transcribe_audio_with_optional_whisper("nonexistent.wav")
    assert whisper_res.available is False


def test_assisted_farmer_without_phone_printable_receipt(
    api_client: TestClient, db_session: Session
) -> None:
    _, crop = _seed_farmer_and_crop(db_session, phone="+919400000004")
    operator = User(
        email="ivr_op@example.com",
        phone_number="+919400000005",
        full_name="Center Operator",
        role=UserRole.OPERATOR,
        password_hash=hash_secret("Pass!123"),
    )
    db_session.add(operator)
    db_session.commit()

    op_token = api_client.post(
        "/api/v1/auth/login",
        json={"identifier": "ivr_op@example.com", "password": "Pass!123"},
    ).json()["access_token"]
    op_hdr = {"Authorization": f"Bearer {op_token}"}

    farmer_res = api_client.post(
        "/api/v1/farmers/assisted",
        json={
            "full_name": "వెంకయ్య (No Phone)",
            "preferred_language": "te",
            "village": "Tadikonda",
            "district": "Guntur",
            "consent_method": "IN_PERSON_VERBAL",
            "consent_confirmed": True,
        },
        headers=op_hdr,
    )
    assert farmer_res.status_code == 201
    farmer_id = farmer_res.json()["farmer_id"]

    listing_res = api_client.post(
        "/api/v1/listings",
        json={
            "farmer_id": farmer_id,
            "crop_id": str(crop.id),
            "quantity_value": 60,
            "quantity_unit": "KG",
            "floor_price_paise_per_kg": 2100,
            "harvested_at": (utc_now() - timedelta(hours=1)).isoformat(),
            "urgency_option": "WITHIN_12H",
            "approx_location_label": "Tadikonda, Guntur",
            "exact_pickup_address": "Center Gate",
            "consent_confirmed": True,
        },
        headers=op_hdr,
    )
    assert listing_res.status_code == 201
    listing_id = listing_res.json()["id"]

    receipt = api_client.get(f"/api/v1/listings/{listing_id}/receipt", headers=op_hdr)
    assert receipt.status_code == 200
    body = receipt.json()
    assert body["farmer_id"] == farmer_id
    assert body["total_quantity_grams"] == 60_000
    assert "Center Operator" in body["operator_or_centre_info"]
