"""Explicitly enabled demo data seeding script for PolamRaksha.

Refuses to execute in production. Requires `--confirm-demo` CLI flag
or `ENABLE_DEMO_SEED=true` environment variable.
"""

import argparse
import os
import sys
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.core.security import hash_secret
from app.db import models as _models  # noqa: F401
from app.db.session import get_session_factory
from app.modules.allocation.models import Allocation, AllocationRun, AllocationRunStatus
from app.modules.auctions.models import Auction, AuctionStatus, BidRevision
from app.modules.listings.models import CropCatalog, ListingStatus, ProduceListing
from app.modules.logistics.models import RoadDistanceCache
from app.modules.market_prices.models import MarketReferencePrice
from app.modules.orders.models import Order, OrderStatus
from app.modules.users.models import (
    AssistedAccessRelationship,
    BuyerProfile,
    FarmerProfile,
    User,
    UserRole,
)
from app.shared.time import utc_now

CROPS = [
    ("TOMATO", "Tomato", "టమాటా", 48),
    ("ONION", "Onion", "ఉల్లిపాయ", 168),
    ("BRINJAL", "Brinjal", "వంకాయ", 72),
    ("OKRA", "Okra", "బెండకాయ", 36),
    ("MANGO", "Mango", "మామిడి", 96),
]


def seed_demo_data(db: Session) -> None:
    """Insert fictional, clearly labelled simulated demo records."""
    now = utc_now()

    crop_map: dict[str, CropCatalog] = {}
    for code, name_en, name_te, shelf_hours in CROPS:
        crop = db.scalar(select(CropCatalog).where(CropCatalog.code == code))
        if crop is None:
            crop = CropCatalog(
                code=code,
                name_en=name_en,
                name_te=name_te,
                default_shelf_life_hours=shelf_hours,
            )
            db.add(crop)
            db.flush()
        crop_map[code] = crop

    def _get_or_create_user(
        *,
        email: str,
        phone: str,
        full_name: str,
        role: UserRole,
        secret: str,
        pin: str | None = None,
    ) -> User:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                phone_number=phone,
                full_name=full_name,
                preferred_language="te" if role in {UserRole.FARMER, UserRole.OPERATOR} else "en",
                role=role,
                password_hash=hash_secret(secret),
                pin_hash=hash_secret(pin) if pin else None,
            )
            db.add(user)
            db.flush()
        return user

    farmer_1 = _get_or_create_user(
        email="demo.farmer1@polamraksha.local",
        phone="+919000000001",
        full_name="రామయ్య (Demo Farmer 1)",
        role=UserRole.FARMER,
        secret="DemoFarmer#2026",
        pin="1234",
    )
    if db.scalar(select(FarmerProfile).where(FarmerProfile.user_id == farmer_1.id)) is None:
        db.add(
            FarmerProfile(
                user_id=farmer_1.id,
                village="Tadikonda",
                mandal="Tadikonda",
                district="Guntur",
                exact_pickup_address="[SIMULATED] Plot 14, Tadikonda Road, Guntur",
                latitude=16.4167,
                longitude=80.4500,
                approx_latitude=16.42,
                approx_longitude=80.45,
            )
        )

    operator_1 = _get_or_create_user(
        email="demo.operator1@polamraksha.local",
        phone="+919000000002",
        full_name="లక్ష్మి (Demo Operator)",
        role=UserRole.OPERATOR,
        secret="DemoOperator#2026",
    )
    if (
        db.scalar(
            select(AssistedAccessRelationship).where(
                AssistedAccessRelationship.operator_id == operator_1.id,
                AssistedAccessRelationship.farmer_id == farmer_1.id,
            )
        )
        is None
    ):
        db.add(
            AssistedAccessRelationship(
                operator_id=operator_1.id,
                farmer_id=farmer_1.id,
                is_active=True,
                notes="[SIMULATED] Demo assisted access",
            )
        )

    buyer_1 = _get_or_create_user(
        email="demo.buyer1@polamraksha.local",
        phone="+919000000003",
        full_name="Sri Venkateswara Traders (Demo Buyer)",
        role=UserRole.BUYER,
        secret="DemoBuyer#2026",
    )
    if db.scalar(select(BuyerProfile).where(BuyerProfile.user_id == buyer_1.id)) is None:
        db.add(
            BuyerProfile(
                user_id=buyer_1.id,
                business_name="Sri Venkateswara Traders (Simulated)",
                buyer_type="wholesaler",
                district="Guntur",
            )
        )

    existing_listing = db.scalar(
        select(ProduceListing).where(
            ProduceListing.farmer_id == farmer_1.id,
            ProduceListing.is_simulated.is_(True),
        )
    )
    if existing_listing is None:
        listing = ProduceListing(
            farmer_id=farmer_1.id,
            created_by_user_id=farmer_1.id,
            crop_id=crop_map["TOMATO"].id,
            status=ListingStatus.ACTIVE,
            total_quantity_grams=500_000,
            available_quantity_grams=400_000,
            reserved_quantity_grams=100_000,
            collected_quantity_grams=0,
            floor_price_paise_per_kg=1800,
            harvested_at=now - timedelta(hours=4),
            spoilage_deadline_at=now + timedelta(hours=40),
            approx_location_label="Tadikonda Mandal, Guntur",
            approx_latitude=16.42,
            approx_longitude=80.45,
            exact_pickup_address="[SIMULATED] Plot 14, Tadikonda Road, Guntur",
            is_simulated=True,
        )
        db.add(listing)
        db.flush()

        auction = Auction(
            listing_id=listing.id,
            status=AuctionStatus.OPEN,
            min_bid_paise_per_kg=1800,
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=6),
            hard_close_at=now + timedelta(hours=6),
        )
        db.add(auction)
        db.flush()

        db.add(
            BidRevision(
                auction_id=auction.id,
                buyer_id=buyer_1.id,
                revision_number=1,
                bid_price_paise_per_kg=2100,
                requested_quantity_grams=100_000,
                min_acceptable_grams=50_000,
                estimated_collection_at=now + timedelta(hours=8),
                standby_until=now + timedelta(hours=10),
                idempotency_key="demo-seed-bid-1",
                is_active=True,
            )
        )

        run = AllocationRun(
            auction_id=auction.id,
            status=AllocationRunStatus.SOLVED,
            solver_status="SIMULATED_DEMO",
            objective_value_paise=210_000,
            completed_at=now,
        )
        db.add(run)
        db.flush()

        alloc = Allocation(
            allocation_run_id=run.id,
            auction_id=auction.id,
            buyer_id=buyer_1.id,
            allocated_quantity_grams=100_000,
            unit_price_paise_per_kg=2100,
            transport_cost_paise=15_000,
        )
        db.add(alloc)
        db.flush()

        db.add(
            Order(
                allocation_id=alloc.id,
                listing_id=listing.id,
                farmer_id=farmer_1.id,
                buyer_id=buyer_1.id,
                status=OrderStatus.CONFIRMED,
                quantity_grams=100_000,
                total_amount_paise=210_000,
                transport_cost_paise=15_000,
                pickup_deadline_at=now + timedelta(hours=12),
                is_simulated=True,
            )
        )

    _get_or_create_user(
        email="demo.admin@polamraksha.local",
        phone="+919000000099",
        full_name="PolamRaksha Demo Admin",
        role=UserRole.ADMIN,
        secret="DemoAdmin#2026",
    )

    # Seed offline cached route-distance samples for Andhra Pradesh mandals
    routes = [
        ("16.4200,80.4500", "16.3100,80.4400", 15200, 1620, "CACHED_MATRIX"),
        ("16.4200,80.4500", "16.5100,80.6500", 29400, 2700, "CACHED_MATRIX"),
        ("16.4200,80.4500", "16.2400,80.6400", 31800, 2940, "CACHED_MATRIX"),
    ]
    for o_key, d_key, dist_m, dur_s, provider in routes:
        if (
            db.scalar(
                select(RoadDistanceCache).where(
                    RoadDistanceCache.origin_key == o_key,
                    RoadDistanceCache.dest_key == d_key,
                )
            )
            is None
        ):
            db.add(
                RoadDistanceCache(
                    origin_key=o_key,
                    dest_key=d_key,
                    distance_meters=dist_m,
                    duration_seconds=dur_s,
                    provider_name=provider,
                )
            )

    # Seed simulated market reference prices
    has_sim_prices = db.scalar(
        select(MarketReferencePrice).where(MarketReferencePrice.is_simulated.is_(True))
    )
    if has_sim_prices is None:
        for code, name_en, name_te, mandi, modal_p in [
            ("TOMATO", "Tomato", "టమాటా", "Guntur Rythu Bazaar", 2400),
            ("ONION", "Onion", "ఉల్లిపాయ", "Tadepalligudem Mandi", 2800),
            ("BRINJAL", "Brinjal", "వంకాయ", "Vijayawada Mandi", 2100),
            ("OKRA", "Okra", "బెండకాయ", "Tenali Mandi", 2600),
            ("MANGO", "Mango", "మామిడి", "Nuzvid Mandi", 4500),
        ]:
            db.add(
                MarketReferencePrice(
                    commodity_code=code,
                    commodity_name_en=name_en,
                    commodity_name_te=name_te,
                    market_name=mandi,
                    district="Guntur",
                    state="Andhra Pradesh",
                    source_name="Simulated Demo Mandi Reference",
                    observed_at=now - timedelta(hours=2),
                    original_unit="KG",
                    original_price_paise=modal_p,
                    normalized_price_paise_per_kg=modal_p,
                    is_simulated=True,
                )
            )

    db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed explicitly enabled demo data.")
    parser.add_argument(
        "--confirm-demo",
        action="store_true",
        help="Confirm seeding simulated demo records into non-production database.",
    )
    args = parser.parse_args()

    settings = get_settings()
    if settings.app_env == "production":
        raise SystemExit("Refusing to seed demo data when APP_ENV=production.")

    env_enabled = os.getenv("ENABLE_DEMO_SEED", "").lower() == "true"
    if not args.confirm_demo and not env_enabled:
        raise SystemExit(
            "Demo seeding is disabled. Pass --confirm-demo or set ENABLE_DEMO_SEED=true."
        )

    session_factory = get_session_factory()
    with session_factory() as db:
        seed_demo_data(db)
    print("Seeded simulated demo data successfully.")


if __name__ == "__main__":
    main()
