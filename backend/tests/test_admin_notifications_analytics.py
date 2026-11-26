from collections.abc import Generator
from datetime import UTC, datetime, timedelta
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
from app.modules.allocation.models import Allocation, AllocationRun, AllocationRunStatus
from app.modules.auctions.models import Auction, AuctionStatus
from app.modules.listings.models import CropCatalog, ListingStatus, ProduceListing
from app.modules.notifications.models import Notification
from app.modules.notifications.service import emit_notification_outbox, process_notification_outbox
from app.modules.orders.models import CollectionRecord, DisputeCase, Order, OrderStatus
from app.modules.system.models import AuditEvent
from app.modules.users.models import BuyerProfile, User, UserRole


@pytest.fixture
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    db_file = tmp_path / "test_phase9.db"
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


def _login(api_client: TestClient, email: str) -> str:
    resp = api_client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": "Password!123"},
    )
    assert resp.status_code == 200
    return str(resp.json()["access_token"])


def test_admin_only_actions_protected_and_audit_logged(
    api_client: TestClient, db_session: Session
) -> None:
    admin = User(
        email="adm_test@example.com",
        phone_number="+919400000001",
        full_name="Admin User",
        role=UserRole.ADMIN,
        password_hash=hash_secret("Password!123"),
    )
    farmer = User(
        email="frm_test@example.com",
        phone_number="+919400000002",
        full_name="Farmer User",
        role=UserRole.FARMER,
        password_hash=hash_secret("Password!123"),
    )
    buyer = User(
        email="buy_test@example.com",
        phone_number="+919400000003",
        full_name="Buyer User",
        role=UserRole.BUYER,
        password_hash=hash_secret("Password!123"),
    )
    db_session.add_all([admin, farmer, buyer])
    db_session.flush()
    db_session.add(
        BuyerProfile(
            user_id=buyer.id,
            business_name="Guntur Fresh Traders",
            district="Guntur",
            state="Andhra Pradesh",
        )
    )
    db_session.commit()

    farmer_token = _login(api_client, "frm_test@example.com")
    admin_token = _login(api_client, "adm_test@example.com")

    # Non-admin must be rejected
    forbidden_resp = api_client.post(
        f"/api/v1/admin/buyers/{buyer.id}/verify",
        json={"verification_status": "VERIFIED", "is_restricted": False},
        headers={"Authorization": f"Bearer {farmer_token}"},
    )
    assert forbidden_resp.status_code == 403

    # Admin can verify buyer and audit event is recorded
    ok_resp = api_client.post(
        f"/api/v1/admin/buyers/{buyer.id}/verify",
        json={"verification_status": "VERIFIED", "is_restricted": False, "notes": "KYC checked"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert ok_resp.status_code == 200
    assert ok_resp.json()["verification_status"] == "VERIFIED"

    audit_rows = db_session.scalars(
        select(AuditEvent).where(AuditEvent.action == "ADMIN_BUYER_VERIFIED")
    ).all()
    assert len(audit_rows) == 1
    assert audit_rows[0].actor_user_id == admin.id


def test_duplicate_notifications_prevented_and_telephone_not_falsely_claimed(
    db_session: Session,
) -> None:
    user = User(
        email="notif_u@example.com",
        phone_number="+919400000010",
        full_name="Notif Farmer",
        role=UserRole.FARMER,
        password_hash=hash_secret("Password!123"),
    )
    db_session.add(user)
    db_session.commit()

    # Emit duplicate event_id twice
    emit_notification_outbox(
        db_session,
        event_id="auction-closed-evt-1",
        event_type="AUCTION_CLOSED",
        recipient_user_ids=[user.id],
        title="Auction Closed",
        body="Your tomato auction closed.",
        channels=["in_app", "telephone"],
    )
    emit_notification_outbox(
        db_session,
        event_id="auction-closed-evt-1",
        event_type="AUCTION_CLOSED",
        recipient_user_ids=[user.id],
        title="Auction Closed",
        body="Your tomato auction closed.",
        channels=["in_app", "telephone"],
    )
    db_session.commit()

    created = process_notification_outbox(db_session)
    db_session.commit()
    assert created == 2

    rows = db_session.scalars(
        select(Notification).where(Notification.user_id == user.id)
    ).all()
    assert len(rows) == 2
    by_channel = {r.channel: r for r in rows}
    assert by_channel["in_app"].status == "DELIVERED"
    assert by_channel["telephone"].status == "FAILED"
    assert "not configured" in (by_channel["telephone"].provider_message or "").lower()


def test_impact_analytics_distinguishes_allocated_collected_cancelled_demo_and_ist_dates(
    api_client: TestClient, db_session: Session
) -> None:
    admin = User(
        email="an_adm@example.com",
        phone_number="+919400000020",
        full_name="Analytics Admin",
        role=UserRole.ADMIN,
        password_hash=hash_secret("Password!123"),
    )
    farmer = User(
        email="an_frm@example.com",
        phone_number="+919400000021",
        full_name="Analytics Farmer",
        role=UserRole.FARMER,
        password_hash=hash_secret("Password!123"),
    )
    buyer = User(
        email="an_buy@example.com",
        phone_number="+919400000022",
        full_name="Analytics Buyer",
        role=UserRole.BUYER,
        password_hash=hash_secret("Password!123"),
    )
    crop = CropCatalog(code="TOMATO", name_en="Tomato", name_te="టమాటా", default_shelf_life_hours=48)
    db_session.add_all([admin, farmer, buyer, crop])
    db_session.flush()

    # 2026-11-25 19:00 UTC == 2026-11-26 00:30 IST (inside 2026-11-26 IST)
    in_ist_day = datetime(2026, 11, 25, 19, 0, 0, tzinfo=UTC)
    # 2026-11-25 17:00 UTC == 2026-11-25 22:30 IST (outside 2026-11-26 IST)
    prev_ist_day = datetime(2026, 11, 25, 17, 0, 0, tzinfo=UTC)

    prod_listing = ProduceListing(
        farmer_id=farmer.id,
        created_by_user_id=farmer.id,
        crop_id=crop.id,
        status=ListingStatus.PARTIALLY_ALLOCATED,
        total_quantity_grams=100_000,
        available_quantity_grams=20_000,
        reserved_quantity_grams=40_000,
        collected_quantity_grams=40_000,
        floor_price_paise_per_kg=2000,
        harvested_at=in_ist_day - timedelta(hours=2),
        spoilage_deadline_at=in_ist_day + timedelta(hours=24),
        approx_location_label="Tenali, Guntur",
        exact_pickup_address="Plot 1",
        urgency_option="WITHIN_24H",
        is_simulated=False,
        created_at=in_ist_day,
    )
    prev_listing = ProduceListing(
        farmer_id=farmer.id,
        created_by_user_id=farmer.id,
        crop_id=crop.id,
        status=ListingStatus.ACTIVE,
        total_quantity_grams=50_000,
        available_quantity_grams=50_000,
        reserved_quantity_grams=0,
        collected_quantity_grams=0,
        floor_price_paise_per_kg=2000,
        harvested_at=prev_ist_day - timedelta(hours=2),
        spoilage_deadline_at=prev_ist_day + timedelta(hours=24),
        approx_location_label="Tenali, Guntur",
        exact_pickup_address="Plot 2",
        is_simulated=False,
        created_at=prev_ist_day,
    )
    demo_listing = ProduceListing(
        farmer_id=farmer.id,
        created_by_user_id=farmer.id,
        crop_id=crop.id,
        status=ListingStatus.ACTIVE,
        total_quantity_grams=999_000,
        available_quantity_grams=999_000,
        reserved_quantity_grams=0,
        collected_quantity_grams=0,
        floor_price_paise_per_kg=2000,
        harvested_at=in_ist_day - timedelta(hours=1),
        spoilage_deadline_at=in_ist_day + timedelta(hours=12),
        approx_location_label="Demo Village",
        exact_pickup_address="Demo Plot",
        is_simulated=True,
        created_at=in_ist_day,
    )
    db_session.add_all([prod_listing, prev_listing, demo_listing])
    db_session.flush()

    auction = Auction(
        listing_id=prod_listing.id,
        status=AuctionStatus.CLOSED,
        min_bid_paise_per_kg=2000,
        starts_at=in_ist_day,
        ends_at=in_ist_day + timedelta(hours=1),
        hard_close_at=in_ist_day + timedelta(hours=2),
    )
    db_session.add(auction)
    db_session.flush()

    run = AllocationRun(
        auction_id=auction.id,
        status=AllocationRunStatus.SOLVED,
        solver_status="OPTIMAL",
        is_approved=True,
        approved_at=in_ist_day,
    )
    db_session.add(run)
    db_session.flush()

    alloc_collected = Allocation(
        allocation_run_id=run.id,
        auction_id=auction.id,
        buyer_id=buyer.id,
        allocated_quantity_grams=40_000,
        unit_price_paise_per_kg=2500,
        transport_cost_paise=0,
    )
    alloc_cancelled = Allocation(
        allocation_run_id=run.id,
        auction_id=auction.id,
        buyer_id=buyer.id,
        allocated_quantity_grams=40_000,
        unit_price_paise_per_kg=2500,
        transport_cost_paise=0,
    )
    db_session.add_all([alloc_collected, alloc_cancelled])
    db_session.flush()

    order_collected = Order(
        allocation_id=alloc_collected.id,
        listing_id=prod_listing.id,
        farmer_id=farmer.id,
        buyer_id=buyer.id,
        status=OrderStatus.COLLECTED,
        quantity_grams=40_000,
        total_amount_paise=100_000,
        transport_cost_paise=0,
        pickup_deadline_at=in_ist_day + timedelta(hours=6),
        is_simulated=False,
        created_at=in_ist_day,
    )
    order_cancelled = Order(
        allocation_id=alloc_cancelled.id,
        listing_id=prod_listing.id,
        farmer_id=farmer.id,
        buyer_id=buyer.id,
        status=OrderStatus.CANCELLED_BY_BUYER,
        quantity_grams=40_000,
        total_amount_paise=100_000,
        transport_cost_paise=0,
        pickup_deadline_at=in_ist_day + timedelta(hours=6),
        is_simulated=False,
        created_at=in_ist_day,
    )
    db_session.add_all([order_collected, order_cancelled])
    db_session.flush()

    db_session.add(
        CollectionRecord(
            order_id=order_collected.id,
            collected_quantity_grams=40_000,
            collected_at=in_ist_day + timedelta(hours=2),
            recorded_by_user_id=farmer.id,
        )
    )
    db_session.add(
        DisputeCase(
            order_id=order_cancelled.id,
            raised_by_user_id=farmer.id,
            reason="Buyer cancelled last minute",
        )
    )
    db_session.commit()

    admin_token = _login(api_client, "an_adm@example.com")
    resp = api_client.get(
        "/api/v1/analytics/impact?start_date=2026-11-26&end_date=2026-11-26&include_simulated=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    prod = body["production"]

    # Date filter in IST includes only 100kg listing, excludes 50kg prev-IST-day and 999kg demo
    assert prod["produce_listed_grams"] == 100_000
    assert prod["produce_allocated_grams"] == 80_000
    assert prod["produce_collected_grams"] == 40_000
    assert prod["cancelled_quantity_grams"] == 40_000
    # Allocated != collected; 24h non-recovered collected produce is surplus collected
    assert prod["surplus_produce_collected_grams"] == 40_000
    assert prod["rescued_from_waste_grams"] == 0
    # Cancelled order (100_000 paise) is NOT counted as completed sales
    assert prod["gross_transaction_value_paise"] == 100_000
    assert prod["estimated_net_sales_revenue_paise"] == 100_000
    assert prod["buyer_completion_rate_percent"] == 50.0

    # Demo metrics are strictly separated and labelled
    demo = body["demo_simulated"]
    assert demo["is_simulated"] is True
    assert demo["produce_listed_grams"] == 999_000
    assert "Simulated" in demo["dataset_label"]

    # Overview matches DB records
    ov = api_client.get(
        "/api/v1/admin/overview",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert ov.status_code == 200
    assert ov.json()["open_disputes_count"] == 1
