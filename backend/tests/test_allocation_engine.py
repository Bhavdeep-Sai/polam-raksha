import itertools
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
from app.modules.allocation.solver import (
    AllocationInput,
    AllocationStrategy,
    BuyerOfferInput,
    SolverStatus,
    _filter_offers,
    _greedy_fallback,
    solve_allocation,
)
from app.modules.auctions.models import Auction, AuctionStatus, BidRevision
from app.modules.listings.models import CropCatalog, ListingStatus, ProduceListing
from app.modules.orders.models import Order
from app.modules.users.models import BuyerProfile, User, UserRole
from app.shared.time import utc_now


def _offer(
    buyer_id: str,
    *,
    price: int,
    min_kg: int,
    max_kg: int,
    var_transport: int = 0,
    fixed_transport: int = 0,
    reliability: int = 100,
    eligible: bool = True,
    hours_offset: int = 2,
) -> BuyerOfferInput:
    base = utc_now()
    return BuyerOfferInput(
        buyer_id=buyer_id,
        unit_price_paise_per_kg=price,
        min_quantity_grams=min_kg * 1000,
        max_quantity_grams=max_kg * 1000,
        estimated_collection_at=base + timedelta(hours=hours_offset),
        farmer_paid_variable_transport_paise_per_kg=var_transport,
        farmer_paid_fixed_pickup_cost_paise=fixed_transport,
        reliability_score=reliability,
        is_eligible=eligible,
    )


def test_single_buyer_entire_lot() -> None:
    deadline = utc_now() + timedelta(hours=10)
    out = solve_allocation(
        AllocationInput(
            available_quantity_grams=100_000,
            committed_quantity_grams=0,
            reserve_price_paise_per_kg=1800,
            hard_collection_deadline=deadline,
            offers=[_offer("b1", price=2200, min_kg=50, max_kg=100)],
        )
    )
    assert out.solver_status == SolverStatus.OPTIMAL
    assert out.total_allocated_grams == 100_000
    assert out.gross_revenue_paise == 220_000
    assert out.estimated_net_revenue_paise == 220_000
    assert out.unallocated_quantity_grams == 0


def test_multiple_buyers_partial_quantities_and_remainder_grams() -> None:
    deadline = utc_now() + timedelta(hours=10)
    out = solve_allocation(
        AllocationInput(
            available_quantity_grams=100_500,
            committed_quantity_grams=20_000,
            reserve_price_paise_per_kg=1800,
            hard_collection_deadline=deadline,
            offers=[
                _offer("b1", price=2200, min_kg=20, max_kg=60),
                _offer("b2", price=2000, min_kg=20, max_kg=60),
            ],
        )
    )
    assert out.solver_status == SolverStatus.OPTIMAL
    assert out.total_allocated_grams == 100_000
    assert out.unallocated_quantity_grams == 500
    assert len(out.selected_buyers) == 2


def test_higher_price_with_higher_transport_cost_vs_rescue_first() -> None:
    deadline = utc_now() + timedelta(hours=10)
    offers = [
        # Net: 2500 - 1000 = 1500/kg, must take 50kg -> 75,000 net
        _offer("high_transport", price=2500, min_kg=50, max_kg=50, var_transport=1000),
        # Net: 2100 - 100 = 2000/kg, max 40kg -> 80,000 net
        _offer("low_transport", price=2100, min_kg=10, max_kg=40, var_transport=100),
    ]
    rev_first = solve_allocation(
        AllocationInput(
            available_quantity_grams=50_000,
            committed_quantity_grams=0,
            reserve_price_paise_per_kg=1800,
            hard_collection_deadline=deadline,
            strategy=AllocationStrategy.REVENUE_FIRST,
            offers=offers,
        )
    )
    assert rev_first.solver_status == SolverStatus.OPTIMAL
    assert rev_first.selected_buyers[0].buyer_id == "low_transport"
    assert rev_first.selected_buyers[0].allocated_quantity_grams == 40_000

    rescue_first = solve_allocation(
        AllocationInput(
            available_quantity_grams=50_000,
            committed_quantity_grams=0,
            reserve_price_paise_per_kg=1800,
            hard_collection_deadline=deadline,
            strategy=AllocationStrategy.RESCUE_FIRST,
            offers=offers,
        )
    )
    assert rescue_first.solver_status == SolverStatus.OPTIMAL
    assert rescue_first.selected_buyers[0].buyer_id == "high_transport"
    assert rescue_first.total_allocated_grams == 50_000


def test_deadline_moq_fixed_cost_and_cancelled_buyer_constraints() -> None:
    deadline = utc_now() + timedelta(hours=5)
    out = solve_allocation(
        AllocationInput(
            available_quantity_grams=50_000,
            committed_quantity_grams=0,
            reserve_price_paise_per_kg=1800,
            hard_collection_deadline=deadline,
            offers=[
                _offer("late_buyer", price=3000, min_kg=10, max_kg=50, hours_offset=8),
                _offer("cancelled_buyer", price=3000, min_kg=10, max_kg=50, eligible=False),
                _offer("too_high_moq", price=2900, min_kg=60, max_kg=80),
                # Fixed pickup cost 20000 paise -> net = 2200*30 - 20000 = 46000
                _offer(
                    "fixed_cost_buyer",
                    price=2200,
                    min_kg=30,
                    max_kg=30,
                    fixed_transport=20_000,
                ),
            ],
        )
    )
    assert out.solver_status == SolverStatus.OPTIMAL
    assert len(out.selected_buyers) == 1
    assert out.selected_buyers[0].buyer_id == "fixed_cost_buyer"
    assert out.transportation_cost_paise == 20_000
    assert out.estimated_net_revenue_paise == 46_000


def test_insufficient_demand_and_infeasible_allocation() -> None:
    deadline = utc_now() + timedelta(hours=10)
    insufficient = solve_allocation(
        AllocationInput(
            available_quantity_grams=100_000,
            committed_quantity_grams=0,
            reserve_price_paise_per_kg=1800,
            hard_collection_deadline=deadline,
            offers=[_offer("small", price=2000, min_kg=10, max_kg=30)],
        )
    )
    assert insufficient.total_allocated_grams == 30_000
    assert insufficient.unallocated_quantity_grams == 70_000

    infeasible = solve_allocation(
        AllocationInput(
            available_quantity_grams=100_000,
            committed_quantity_grams=0,
            reserve_price_paise_per_kg=1800,
            hard_collection_deadline=deadline,
            min_net_revenue_paise=500_000,
            offers=[_offer("small", price=2000, min_kg=10, max_kg=30)],
        )
    )
    assert infeasible.solver_status == SolverStatus.INFEASIBLE
    assert infeasible.selected_buyers == []


def test_equal_offers_deterministic_tie_breaking_and_fallback() -> None:
    deadline = utc_now() + timedelta(hours=10)
    inp = AllocationInput(
        available_quantity_grams=50_000,
        committed_quantity_grams=0,
        reserve_price_paise_per_kg=1800,
        hard_collection_deadline=deadline,
        offers=[
            _offer("b_low_rel", price=2200, min_kg=50, max_kg=50, reliability=60),
            _offer("b_high_rel", price=2200, min_kg=50, max_kg=50, reliability=95),
        ],
    )
    out = solve_allocation(inp)
    assert out.solver_status == SolverStatus.OPTIMAL
    assert out.selected_buyers[0].buyer_id == "b_high_rel"

    # Direct fallback check: clearly labelled and constraint-safe
    prepared, explanations, avail_kg = _filter_offers(inp)
    fb = _greedy_fallback(inp, prepared, explanations, avail_kg, 0)
    assert fb.used_fallback is True
    assert fb.solver_status == SolverStatus.FEASIBLE
    assert fb.selected_buyers[0].buyer_id == "b_high_rel"


def test_exhaustive_enumeration_matches_cp_sat_on_small_instance() -> None:
    """Verify CP-SAT optimality against brute-force enumeration for small instances."""
    deadline = utc_now() + timedelta(hours=10)
    avail_kg = 6
    offers = [
        _offer("b1", price=2400, min_kg=2, max_kg=4, fixed_transport=1000, reliability=90),
        _offer("b2", price=2200, min_kg=1, max_kg=3, var_transport=100, reliability=80),
        _offer("b3", price=2500, min_kg=3, max_kg=5, fixed_transport=2500, reliability=70),
    ]

    def brute_force_best(strategy: AllocationStrategy) -> tuple[int, int]:
        best_tuple = (-10**18, -10**18)
        for q1, q2, q3 in itertools.product(range(5), range(4), range(6)):
            if q1 not in (0, 2, 3, 4) or q2 not in (0, 1, 2, 3) or q3 not in (0, 3, 4, 5):
                continue
            total_q = q1 + q2 + q3
            if total_q > avail_kg:
                continue
            net = (
                q1 * 2400 - (1000 if q1 > 0 else 0)
                + q2 * (2200 - 100)
                + q3 * 2500 - (2500 if q3 > 0 else 0)
            )
            key = (net, total_q) if strategy == AllocationStrategy.REVENUE_FIRST else (total_q, net)
            if key > best_tuple:
                best_tuple = key
        return best_tuple

    for strat in (AllocationStrategy.REVENUE_FIRST, AllocationStrategy.RESCUE_FIRST):
        expected_primary, expected_secondary = brute_force_best(strat)
        out = solve_allocation(
            AllocationInput(
                available_quantity_grams=avail_kg * 1000,
                committed_quantity_grams=0,
                reserve_price_paise_per_kg=1800,
                hard_collection_deadline=deadline,
                strategy=strat,
                offers=offers,
            )
        )
        assert out.solver_status == SolverStatus.OPTIMAL
        actual_pair = (
            (out.estimated_net_revenue_paise, out.total_allocated_grams // 1000)
            if strat == AllocationStrategy.REVENUE_FIRST
            else (out.total_allocated_grams // 1000, out.estimated_net_revenue_paise)
        )
        assert actual_pair == (expected_primary, expected_secondary)


@pytest.fixture
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    db_file = tmp_path / "test_phase6.db"
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


def test_allocation_persistence_stale_revalidation_and_approval(
    api_client: TestClient, db_session: Session
) -> None:
    now = utc_now()
    crop = CropCatalog(code="TOMATO", name_en="Tomato", name_te="టమాటా", default_shelf_life_hours=48)
    farmer = User(
        email="alloc_f@example.com",
        phone_number="+919500000001",
        full_name="Alloc Farmer",
        role=UserRole.FARMER,
        password_hash=hash_secret("Pass!123"),
    )
    buyer = User(
        email="alloc_b@example.com",
        phone_number="+919500000002",
        full_name="Alloc Buyer",
        role=UserRole.BUYER,
        password_hash=hash_secret("Pass!123"),
    )
    db_session.add_all([crop, farmer, buyer])
    db_session.flush()
    db_session.add(BuyerProfile(user_id=buyer.id, business_name="AB", district="Guntur"))

    listing = ProduceListing(
        farmer_id=farmer.id,
        created_by_user_id=farmer.id,
        crop_id=crop.id,
        status=ListingStatus.ACTIVE,
        total_quantity_grams=100_000,
        available_quantity_grams=100_000,
        reserved_quantity_grams=0,
        collected_quantity_grams=0,
        floor_price_paise_per_kg=1800,
        harvested_at=now - timedelta(hours=1),
        spoilage_deadline_at=now + timedelta(hours=10),
        approx_location_label="Guntur",
        exact_pickup_address="Plot 1",
        auto_allocate_approved=False,
    )
    db_session.add(listing)
    db_session.flush()

    auction = Auction(
        listing_id=listing.id,
        status=AuctionStatus.CLOSED,
        min_bid_paise_per_kg=1800,
        starts_at=now - timedelta(hours=2),
        ends_at=now - timedelta(minutes=5),
        hard_close_at=now + timedelta(hours=1),
    )
    db_session.add(auction)
    db_session.flush()

    db_session.add(
        BidRevision(
            auction_id=auction.id,
            buyer_id=buyer.id,
            revision_number=1,
            bid_price_paise_per_kg=2200,
            requested_quantity_grams=80_000,
            min_acceptable_grams=40_000,
            estimated_collection_at=now + timedelta(hours=4),
            standby_until=now + timedelta(hours=6),
            idempotency_key="alloc-bid-1",
            is_active=True,
        )
    )
    db_session.commit()

    f_token = api_client.post(
        "/api/v1/auth/login",
        json={"identifier": "alloc_f@example.com", "password": "Pass!123"},
    ).json()["access_token"]
    f_hdr = {"Authorization": f"Bearer {f_token}"}

    run_res = api_client.post(
        f"/api/v1/allocations/auctions/{auction.id}/run",
        json={"strategy": "REVENUE_FIRST"},
        headers=f_hdr,
    )
    assert run_res.status_code == 201, run_res.text
    run_id = run_res.json()["id"]
    assert run_res.json()["is_approved"] is False
    assert run_res.json()["estimated_net_revenue_paise"] == 176_000

    # Simulate stale inventory before approval -> must fail with 409
    listing.available_quantity_grams = 50_000
    db_session.commit()
    stale_res = api_client.post(f"/api/v1/allocations/{run_id}/approve", headers=f_hdr)
    assert stale_res.status_code == 409
    assert stale_res.json()["error"]["code"] == "stale_allocation_inventory"

    # Restore inventory and approve -> reserves 80 kg and creates Order
    listing.available_quantity_grams = 100_000
    db_session.commit()
    approve_res = api_client.post(f"/api/v1/allocations/{run_id}/approve", headers=f_hdr)
    assert approve_res.status_code == 200
    assert approve_res.json()["is_approved"] is True
    db_session.refresh(listing)
    assert listing.available_quantity_grams == 20_000
    assert listing.reserved_quantity_grams == 80_000
    assert listing.status == ListingStatus.PARTIALLY_ALLOCATED
    orders = db_session.scalars(select(Order)).all()
    assert len(orders) == 1
    assert orders[0].quantity_grams == 80_000
