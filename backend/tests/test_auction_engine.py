import os
import uuid
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from starlette.websockets import WebSocketDisconnect

from alembic import command
from app.core.security import create_access_token, hash_secret
from app.db import models as _models  # noqa: F401
from app.db.session import get_db
from app.main import app
from app.modules.auctions.models import Auction, AuctionStatus, BidRevision
from app.modules.auctions.schemas import PlaceBidRequest
from app.modules.auctions.service import place_or_revise_bid
from app.modules.listings.models import CropCatalog, ListingStatus, ProduceListing
from app.modules.system.models import ScheduledJob, TransactionalOutboxEvent
from app.modules.users.models import BuyerProfile, User, UserRole
from app.shared.time import utc_now
from app.workers.jobs import enqueue_job, process_due_jobs


@pytest.fixture
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    db_file = tmp_path / "test_phase5.db"
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


def _setup_open_auction(
    db: Session,
    *,
    ends_in_seconds: int = 3600,
    hard_close_in_seconds: int = 4200,
) -> tuple[User, User, User, ProduceListing, Auction]:
    now = utc_now()
    crop = CropCatalog(code="TOMATO", name_en="Tomato", name_te="టమాటా", default_shelf_life_hours=48)
    farmer = User(
        email="auc_farmer@example.com",
        phone_number="+919600000001",
        full_name="Auction Farmer",
        role=UserRole.FARMER,
        password_hash=hash_secret("Pass!123"),
    )
    buyer1 = User(
        email="auc_buyer1@example.com",
        phone_number="+919600000002",
        full_name="Buyer One",
        role=UserRole.BUYER,
        password_hash=hash_secret("Pass!123"),
    )
    buyer2 = User(
        email="auc_buyer2@example.com",
        phone_number="+919600000003",
        full_name="Buyer Two",
        role=UserRole.BUYER,
        password_hash=hash_secret("Pass!123"),
    )
    db.add_all([crop, farmer, buyer1, buyer2])
    db.flush()

    db.add_all([
        BuyerProfile(user_id=buyer1.id, business_name="B1", district="Guntur"),
        BuyerProfile(user_id=buyer2.id, business_name="B2", district="Guntur"),
    ])

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
        spoilage_deadline_at=now + timedelta(hours=12),
        approx_location_label="Tadikonda, Guntur",
        exact_pickup_address="Plot 1",
    )
    db.add(listing)
    db.flush()

    auction = Auction(
        listing_id=listing.id,
        status=AuctionStatus.OPEN,
        min_bid_paise_per_kg=2000,
        min_increment_paise_per_kg=50,
        starts_at=now - timedelta(minutes=5),
        ends_at=now + timedelta(seconds=ends_in_seconds),
        hard_close_at=now + timedelta(seconds=hard_close_in_seconds),
    )
    db.add(auction)
    db.commit()
    return farmer, buyer1, buyer2, listing, auction


def _auth_header(client: TestClient, email: str) -> dict[str, str]:
    res = client.post("/api/v1/auth/login", json={"identifier": email, "password": "Pass!123"})
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_buyers_can_increase_bids_and_revisions_are_immutable(
    api_client: TestClient, db_session: Session
) -> None:
    _, buyer1, buyer2, _, auction = _setup_open_auction(db_session)
    b1_hdr = _auth_header(api_client, buyer1.email or "")
    b2_hdr = _auth_header(api_client, buyer2.email or "")
    now = utc_now()

    bid1 = api_client.post(
        f"/api/v1/auctions/{auction.id}/bids",
        json={
            "bid_price_paise_per_kg": 2100,
            "requested_quantity_grams": 100_000,
            "min_acceptable_grams": 50_000,
            "estimated_collection_at": (now + timedelta(hours=4)).isoformat(),
            "standby_until": (now + timedelta(hours=6)).isoformat(),
            "idempotency_key": "idem-b1-1",
        },
        headers=b1_hdr,
    )
    assert bid1.status_code == 201, bid1.text
    assert bid1.json()["highest_unit_price_paise_per_kg"] == 2100

    # Competing full-lot bid below min increment (2100 + 50 = 2150) is rejected
    bad_inc = api_client.post(
        f"/api/v1/auctions/{auction.id}/bids",
        json={
            "bid_price_paise_per_kg": 2120,
            "requested_quantity_grams": 100_000,
            "min_acceptable_grams": 100_000,
            "estimated_collection_at": (now + timedelta(hours=4)).isoformat(),
            "standby_until": (now + timedelta(hours=6)).isoformat(),
            "idempotency_key": "idem-b2-bad",
        },
        headers=b2_hdr,
    )
    assert bad_inc.status_code == 422
    assert bad_inc.json()["error"]["code"] == "bid_below_minimum_increment"

    # Partial-quantity offer does not need to exceed unrelated full-lot offer
    partial = api_client.post(
        f"/api/v1/auctions/{auction.id}/bids",
        json={
            "bid_price_paise_per_kg": 2050,
            "requested_quantity_grams": 40_000,
            "min_acceptable_grams": 20_000,
            "estimated_collection_at": (now + timedelta(hours=4)).isoformat(),
            "standby_until": (now + timedelta(hours=6)).isoformat(),
            "idempotency_key": "idem-b2-partial",
        },
        headers=b2_hdr,
    )
    assert partial.status_code == 201

    # Buyer 1 increases bid -> revision 2 created, revision 1 preserved in DB
    rev2 = api_client.post(
        f"/api/v1/auctions/{auction.id}/bids",
        json={
            "bid_price_paise_per_kg": 2200,
            "requested_quantity_grams": 100_000,
            "min_acceptable_grams": 50_000,
            "estimated_collection_at": (now + timedelta(hours=4)).isoformat(),
            "standby_until": (now + timedelta(hours=6)).isoformat(),
            "idempotency_key": "idem-b1-2",
        },
        headers=b1_hdr,
    )
    assert rev2.status_code == 201
    assert len(rev2.json()["my_bid_revisions"]) == 2
    b1_revs = db_session.scalars(
        select(BidRevision).where(
            BidRevision.auction_id == auction.id,
            BidRevision.buyer_id == buyer1.id,
        )
    ).all()
    assert len(b1_revs) == 2
    assert sum(1 for r in b1_revs if r.is_active) == 1


def test_duplicate_idempotent_and_late_or_invalid_bids_rejected(
    api_client: TestClient, db_session: Session
) -> None:
    _, buyer1, _, _, auction = _setup_open_auction(db_session)
    b1_hdr = _auth_header(api_client, buyer1.email or "")
    now = utc_now()

    payload = {
        "bid_price_paise_per_kg": 2100,
        "requested_quantity_grams": 50_000,
        "min_acceptable_grams": 25_000,
        "estimated_collection_at": (now + timedelta(hours=3)).isoformat(),
        "standby_until": (now + timedelta(hours=5)).isoformat(),
        "idempotency_key": "idem-same-key",
    }
    first = api_client.post(f"/api/v1/auctions/{auction.id}/bids", json=payload, headers=b1_hdr)
    assert first.status_code == 201

    # Replay with identical key & payload returns same snapshot without creating revision 2
    replay = api_client.post(f"/api/v1/auctions/{auction.id}/bids", json=payload, headers=b1_hdr)
    assert replay.status_code == 201
    assert replay.json()["version"] == first.json()["version"]
    assert len(replay.json()["my_bid_revisions"]) == 1

    # Below reserve rejected
    below_reserve = api_client.post(
        f"/api/v1/auctions/{auction.id}/bids",
        json={**payload, "bid_price_paise_per_kg": 1500, "idempotency_key": "idem-low"},
        headers=b1_hdr,
    )
    assert below_reserve.status_code == 422
    assert below_reserve.json()["error"]["code"] == "bid_below_reserve"

    # Late bid after ends_at rejected
    auction.ends_at = now - timedelta(seconds=5)
    db_session.commit()
    late = api_client.post(
        f"/api/v1/auctions/{auction.id}/bids",
        json={**payload, "bid_price_paise_per_kg": 2300, "idempotency_key": "idem-late"},
        headers=b1_hdr,
    )
    assert late.status_code == 409
    assert late.json()["error"]["code"] == "auction_closed"


def test_soft_close_respects_hard_deadline_and_worker_closes_once(
    api_client: TestClient, db_session: Session
) -> None:
    # Ends in 60s (inside 120s trigger window), hard close in 150s
    _, buyer1, _, _, auction = _setup_open_auction(
        db_session, ends_in_seconds=60, hard_close_in_seconds=150
    )
    b1_hdr = _auth_header(api_client, buyer1.email or "")
    now = utc_now()

    enqueue_job(
        db_session,
        job_type="AUCTION_CLOSE",
        payload={"auction_id": str(auction.id)},
        run_at=auction.ends_at,
    )
    db_session.commit()

    res = api_client.post(
        f"/api/v1/auctions/{auction.id}/bids",
        json={
            "bid_price_paise_per_kg": 2100,
            "requested_quantity_grams": 100_000,
            "min_acceptable_grams": 50_000,
            "estimated_collection_at": (now + timedelta(hours=3)).isoformat(),
            "standby_until": (now + timedelta(hours=5)).isoformat(),
            "idempotency_key": "idem-soft-1",
        },
        headers=b1_hdr,
    )
    assert res.status_code == 201
    body = res.json()
    assert body["soft_closed_triggered"] is True
    assert body["status"] == AuctionStatus.CLOSING.value
    assert body["ends_at"] <= body["hard_close_at"]

    # Process due jobs after ends_at -> auction closes exactly once
    closed_count = process_due_jobs(db_session, now=utc_now() + timedelta(minutes=10))
    assert closed_count >= 1
    db_session.refresh(auction)
    assert auction.status == AuctionStatus.CLOSED

    # Running again does not double-close
    second_count = process_due_jobs(db_session, now=utc_now() + timedelta(minutes=11))
    assert second_count == 0
    closed_events = db_session.scalars(
        select(TransactionalOutboxEvent).where(
            TransactionalOutboxEvent.aggregate_id == auction.id,
            TransactionalOutboxEvent.event_type == "AUCTION_CLOSED",
        )
    ).all()
    assert len(closed_events) == 1

    # Pending jobs remain persisted in DB
    jobs = db_session.scalars(select(ScheduledJob)).all()
    assert any(j.job_type == "APPROVAL_DEADLINE" and j.status == "PENDING" for j in jobs)


def test_websocket_requires_auth_and_sends_snapshot(
    api_client: TestClient, db_session: Session
) -> None:
    _, buyer1, _, _, auction = _setup_open_auction(db_session)

    # Unauthorized WebSocket must be rejected
    with pytest.raises(WebSocketDisconnect):
        with api_client.websocket_connect(f"/ws/auctions/{auction.id}"):
            pass

    from app.core.config import get_settings

    token, _ = create_access_token(
        user_id=buyer1.id, role=buyer1.role, settings=get_settings()
    )

    # Authenticated WebSocket receives snapshot envelope
    with pytest.MonkeyPatch.context() as mp:
        from app.modules.auctions import router as auctions_router

        mp.setattr(
            auctions_router,
            "get_session_factory",
            lambda: sessionmaker(bind=db_session.get_bind()),
        )
        with api_client.websocket_connect(
            f"/ws/auctions/{auction.id}?token={token}"
        ) as ws:
            msg = ws.receive_json()
            assert msg["event_type"] == "AUCTION_SNAPSHOT"
            assert msg["auction_id"] == str(auction.id)
            assert msg["entity_version"] == 1


def test_postgresql_concurrent_bids_remain_consistent() -> None:
    """Run real concurrent bid threads against PostgreSQL using SELECT ... FOR UPDATE."""
    pg_url = os.getenv(
        "TEST_POSTGRES_URL",
        "postgresql+psycopg://polamraksha:polamraksha_dev_pass@localhost:5432/polamraksha",
    )
    engine = create_engine(pg_url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
    except OperationalError as exc:
        engine.dispose()
        pytest.skip(f"PostgreSQL unavailable for concurrency test: {exc}")

    alembic_cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", pg_url)
    command.upgrade(alembic_cfg, "head")

    pg_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with pg_session_local() as setup_db:
        _, buyer1, buyer2, _, auction = _setup_open_auction(setup_db)
        auction_id = auction.id
        buyer1_id = buyer1.id
        buyer2_id = buyer2.id

    def _submit(buyer_id: uuid.UUID, price: int, key: str) -> str:
        with pg_session_local() as thread_db:
            buyer = thread_db.scalar(select(User).where(User.id == buyer_id))
            assert buyer is not None
            now = utc_now()
            try:
                place_or_revise_bid(
                    thread_db,
                    auction_id=auction_id,
                    buyer=buyer,
                    payload=PlaceBidRequest(
                        bid_price_paise_per_kg=price,
                        requested_quantity_grams=100_000,
                        min_acceptable_grams=50_000,
                        estimated_collection_at=now + timedelta(hours=3),
                        standby_until=now + timedelta(hours=5),
                        idempotency_key=key,
                    ),
                )
                return "ok"
            except Exception as exc:
                return str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_submit, buyer1_id, 2100, f"pg-c1-{uuid.uuid4()}")
        f2 = pool.submit(_submit, buyer2_id, 2100, f"pg-c2-{uuid.uuid4()}")
        results = [f1.result(), f2.result()]

    # Exactly one full-lot bid at 2100 succeeds; the second must be rejected by increment rule!
    assert results.count("ok") == 1
    engine.dispose()
