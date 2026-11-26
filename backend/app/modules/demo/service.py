import uuid
from datetime import UTC, timedelta

from fastapi import status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import hash_secret
from app.modules.allocation.models import Allocation, AllocationRun
from app.modules.allocation.schemas import RunAllocationRequest
from app.modules.allocation.service import approve_allocation_run, run_allocation_for_auction
from app.modules.allocation.solver import AllocationStrategy
from app.modules.auctions.models import Auction, AuctionStatus, BidRevision
from app.modules.auctions.schemas import PlaceBidRequest
from app.modules.auctions.service import place_or_revise_bid
from app.modules.listings.models import CropCatalog, ListingStatus, ProduceListing
from app.modules.notifications.service import emit_notification_outbox, process_notification_outbox
from app.modules.orders.models import CollectionRecord, DisputeCase, Order, OrderStatus
from app.modules.reliability.models import BuyerReliabilityEvent
from app.modules.system.models import AuditEvent
from app.modules.users.models import BuyerProfile, FarmerProfile, User, UserRole
from app.shared.time import utc_now
from app.workers.jobs import close_auction_idempotent


def ensure_demo_mode(settings: Settings) -> None:
    if settings.app_env == "production" or not settings.demo_mode_enabled:
        raise AppError(
            code="demo_mode_disabled",
            message=(
                "Demo controls are only available when DEMO_MODE_ENABLED=true outside production"
            ),
            status_code=status.HTTP_403_FORBIDDEN,
        )


def _record_demo_audit(
    db: Session, *, admin: User, action: str, resource_id: str, detail: str
) -> None:
    db.add(
        AuditEvent(
            actor_user_id=admin.id,
            action=action,
            resource_type="demo_scenario",
            resource_id=resource_id,
            metadata_json={"detail": detail, "demo_mode": True},
        )
    )


def _ensure_demo_actors(db: Session) -> tuple[User, list[User], CropCatalog]:
    crop = db.scalar(select(CropCatalog).where(CropCatalog.code == "TOMATO"))
    if crop is None:
        crop = CropCatalog(
            code="TOMATO",
            name_en="Tomato",
            name_te="టమాటా",
            default_shelf_life_hours=48,
        )
        db.add(crop)
        db.flush()

    farmer = db.scalar(select(User).where(User.email == "demo.farmer1@polamraksha.local"))
    if farmer is None:
        farmer = User(
            email="demo.farmer1@polamraksha.local",
            phone_number="+919000000001",
            full_name="రామయ్య (Demo Farmer 1)",
            preferred_language="te",
            role=UserRole.FARMER,
            password_hash=hash_secret("DemoFarmer#2026"),
            pin_hash=hash_secret("1234"),
        )
        db.add(farmer)
        db.flush()
        db.add(
            FarmerProfile(
                user_id=farmer.id,
                village="Tadikonda",
                mandal="Tadikonda",
                district="Guntur",
                exact_pickup_address="[SIMULATED] Plot 14, Tadikonda Road, Guntur",
                approx_latitude=16.42,
                approx_longitude=80.45,
            )
        )

    buyers: list[User] = []
    for idx, (email, phone, name, bname) in enumerate(
        [
            ("demo.buyer1@polamraksha.local", "+919000000011", "Demo Buyer 1", "Guntur Fresh"),
            ("demo.buyer2@polamraksha.local", "+919000000012", "Demo Buyer 2", "Vijayawada Mart"),
            ("demo.buyer3@polamraksha.local", "+919000000013", "Demo Buyer 3", "Tenali Traders"),
        ],
        start=1,
    ):
        buyer = db.scalar(select(User).where(User.email == email))
        if buyer is None:
            buyer = User(
                email=email,
                phone_number=phone,
                full_name=name,
                preferred_language="en",
                role=UserRole.BUYER,
                password_hash=hash_secret("DemoBuyer#2026"),
            )
            db.add(buyer)
            db.flush()
            db.add(
                BuyerProfile(
                    user_id=buyer.id,
                    business_name=bname,
                    district="Guntur",
                    verification_status="VERIFIED",
                    reliability_score=95 - idx * 3,
                )
            )
        buyers.append(buyer)

    db.flush()
    return farmer, buyers, crop


def start_demo_scenario(
    db: Session, *, admin: User, settings: Settings
) -> dict[str, object]:
    """Create a 300 kg Tomato demo listing with accelerated auction duration."""
    now = utc_now()
    farmer, _buyers, crop = _ensure_demo_actors(db)
    duration_sec = settings.demo_auction_duration_seconds

    listing = ProduceListing(
        farmer_id=farmer.id,
        created_by_user_id=farmer.id,
        crop_id=crop.id,
        status=ListingStatus.ACTIVE,
        total_quantity_grams=300_000,
        available_quantity_grams=300_000,
        reserved_quantity_grams=0,
        collected_quantity_grams=0,
        floor_price_paise_per_kg=2000,
        harvested_at=now - timedelta(hours=1),
        spoilage_deadline_at=now + timedelta(hours=12),
        approx_location_label="[DEMO] Tadikonda Mandal, Guntur",
        approx_latitude=16.42,
        approx_longitude=80.45,
        exact_pickup_address="[SIMULATED] Plot 14, Tadikonda Road, Guntur",
        exact_latitude=16.4167,
        exact_longitude=80.4512,
        urgency_option="WITHIN_12H",
        is_simulated=True,
    )
    db.add(listing)
    db.flush()

    auction = Auction(
        listing_id=listing.id,
        status=AuctionStatus.OPEN,
        min_bid_paise_per_kg=2000,
        min_increment_paise_per_kg=50,
        starts_at=now,
        ends_at=now + timedelta(seconds=duration_sec),
        hard_close_at=now + timedelta(seconds=duration_sec + 60),
    )
    db.add(auction)
    db.flush()

    _record_demo_audit(
        db,
        admin=admin,
        action="DEMO_SCENARIO_STARTED",
        resource_id=str(listing.id),
        detail=f"Started 300 kg Tomato demo listing with {duration_sec}s auction",
    )
    db.commit()
    return {
        "listing_id": str(listing.id),
        "auction_id": str(auction.id),
        "quantity_grams": listing.total_quantity_grams,
        "ends_at": auction.ends_at.isoformat(),
    }


def simulate_demo_bids(
    db: Session, *, admin: User, auction_id: uuid.UUID
) -> dict[str, object]:
    """Submit competitive offers from 3 demo buyers + 1 bid increase via domain service."""
    now = utc_now()
    _farmer, buyers, _crop = _ensure_demo_actors(db)

    specs = [
        (buyers[0], 2200, 150_000, 50_000, f"demo-b1-r1-{auction_id}"),
        (buyers[1], 2400, 150_000, 50_000, f"demo-b2-r1-{auction_id}"),
        (buyers[2], 2150, 120_000, 40_000, f"demo-b3-r1-{auction_id}"),
        (buyers[0], 2500, 180_000, 50_000, f"demo-b1-r2-{auction_id}"),
    ]
    for buyer, price, max_g, min_g, idem in specs:
        place_or_revise_bid(
            db,
            auction_id=auction_id,
            buyer=buyer,
            payload=PlaceBidRequest(
                bid_price_paise_per_kg=price,
                requested_quantity_grams=max_g,
                min_acceptable_grams=min_g,
                estimated_collection_at=now + timedelta(hours=3),
                transport_responsibility="BUYER_PICKUP",
                estimated_transport_cost_paise=0,
                standby_until=now + timedelta(hours=8),
                idempotency_key=idem,
            ),
        )

    _record_demo_audit(
        db,
        admin=admin,
        action="DEMO_BIDS_SIMULATED",
        resource_id=str(auction_id),
        detail="Simulated 3 buyers + 1 competitive bid increase",
    )
    db.commit()
    return {"auction_id": str(auction_id), "bids_placed": len(specs)}


def advance_demo_auction_and_allocate(
    db: Session, *, admin: User, auction_id: uuid.UUID
) -> dict[str, object]:
    """Close demo auction at accelerated deadline, run CP-SAT allocation, and approve."""
    auction = db.scalar(select(Auction).where(Auction.id == auction_id))
    if auction is None:
        raise AppError(
            code="auction_not_found",
            message="Demo auction not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    now = utc_now()
    if auction.status in {AuctionStatus.OPEN, AuctionStatus.CLOSING}:
        ends_at = (
            auction.ends_at.replace(tzinfo=UTC)
            if auction.ends_at.tzinfo is None
            else auction.ends_at
        )
        close_time = max(now, ends_at + timedelta(seconds=1))
        close_auction_idempotent(db, auction_id=auction.id, now=close_time)
        db.commit()

    farmer = db.scalar(select(User).where(User.email == "demo.farmer1@polamraksha.local"))
    if farmer is None:
        raise AppError(code="demo_farmer_missing", message="Demo farmer missing", status_code=404)

    run_resp = run_allocation_for_auction(
        db,
        auction_id=auction.id,
        payload=RunAllocationRequest(strategy=AllocationStrategy.REVENUE_FIRST),
        current_user=farmer,
    )
    approved_resp = approve_allocation_run(db, run_id=run_resp.id, current_user=farmer)

    orders = list(
        db.scalars(select(Order).where(Order.listing_id == auction.listing_id)).all()
    )
    for o in orders:
        o.is_simulated = True
        o.status = OrderStatus.CONFIRMED

    _record_demo_audit(
        db,
        admin=admin,
        action="DEMO_AUCTION_ALLOCATED",
        resource_id=str(auction.id),
        detail=(
            f"Closed auction, ran CP-SAT ({approved_resp.solver_status}), "
            f"confirmed {len(orders)} orders"
        ),
    )
    db.commit()
    return {
        "auction_id": str(auction.id),
        "allocation_run_id": str(approved_resp.id),
        "solver_status": approved_resp.solver_status,
        "orders_created": len(orders),
    }


def simulate_demo_cancellation_and_recovery(
    db: Session, *, admin: User, auction_id: uuid.UUID
) -> dict[str, object]:
    """Cancel one confirmed demo order, release only its qty, and re-allocate standby buyer."""
    auction = db.scalar(select(Auction).where(Auction.id == auction_id))
    if auction is None:
        raise AppError(code="auction_not_found", message="Auction not found", status_code=404)
    listing = db.scalar(select(ProduceListing).where(ProduceListing.id == auction.listing_id))
    if listing is None:
        raise AppError(code="listing_not_found", message="Listing not found", status_code=404)

    orders = list(
        db.scalars(
            select(Order)
            .where(Order.listing_id == listing.id, Order.status == OrderStatus.CONFIRMED)
            .order_by(Order.quantity_grams.asc())
        ).all()
    )
    if not orders:
        raise AppError(
            code="no_confirmed_demo_orders",
            message="No confirmed demo orders to cancel",
            status_code=400,
        )

    cancelled_order = orders[0]
    cancelled_qty = cancelled_order.quantity_grams
    cancelled_order.status = OrderStatus.CANCELLED_BY_BUYER
    listing.reserved_quantity_grams = max(0, listing.reserved_quantity_grams - cancelled_qty)
    listing.available_quantity_grams += cancelled_qty
    listing.status = ListingStatus.PARTIALLY_ALLOCATED

    db.add(
        BuyerReliabilityEvent(
            buyer_id=cancelled_order.buyer_id,
            order_id=cancelled_order.id,
            event_type="DEMO_BUYER_CANCELLATION",
            score_delta=-10,
            reason="Simulated buyer cancellation for recovery demonstration",
        )
    )

    # Mark cancelling buyer's bid ineligible so standby buyer receives recovery offer
    bad_bids = db.scalars(
        select(BidRevision).where(
            BidRevision.auction_id == auction.id,
            BidRevision.buyer_id == cancelled_order.buyer_id,
        )
    ).all()
    for b in bad_bids:
        b.is_active = False

    emit_notification_outbox(
        db,
        event_id=f"demo-cancel-{cancelled_order.id}",
        event_type="BUYER_CANCELLATION",
        recipient_user_ids=[listing.farmer_id],
        title="Buyer Cancelled Order",
        body=f"{cancelled_qty / 1000:.1f} kg released for standby recovery.",
    )
    process_notification_outbox(db)
    db.commit()

    # Run recovery allocation for released quantity
    farmer = db.scalar(select(User).where(User.id == listing.farmer_id))
    assert farmer is not None
    rec_run = run_allocation_for_auction(
        db,
        auction_id=auction.id,
        payload=RunAllocationRequest(strategy=AllocationStrategy.RESCUE_FIRST),
        current_user=farmer,
    )
    recovered_orders = 0
    if rec_run.allocations:
        approve_allocation_run(db, run_id=rec_run.id, current_user=farmer)
        new_orders = db.scalars(
            select(Order).where(
                Order.listing_id == listing.id,
                Order.status == OrderStatus.PENDING_CONFIRMATION,
            )
        ).all()
        for no in new_orders:
            no.is_simulated = True
            no.status = OrderStatus.RECOVERED
            recovered_orders += 1

    _record_demo_audit(
        db,
        admin=admin,
        action="DEMO_RECOVERY_EXECUTED",
        resource_id=str(cancelled_order.id),
        detail=f"Released {cancelled_qty}g and created {recovered_orders} recovery order(s)",
    )
    db.commit()
    return {
        "cancelled_order_id": str(cancelled_order.id),
        "released_grams": cancelled_qty,
        "recovered_orders": recovered_orders,
    }


def record_demo_collection(
    db: Session, *, admin: User, auction_id: uuid.UUID
) -> dict[str, object]:
    """Record collection on confirmed/recovered demo orders so analytics update."""
    auction = db.scalar(select(Auction).where(Auction.id == auction_id))
    if auction is None:
        raise AppError(code="auction_not_found", message="Auction not found", status_code=404)
    listing = db.scalar(select(ProduceListing).where(ProduceListing.id == auction.listing_id))
    if listing is None:
        raise AppError(code="listing_not_found", message="Listing not found", status_code=404)

    orders = list(
        db.scalars(
            select(Order).where(
                Order.listing_id == listing.id,
                Order.status.in_([OrderStatus.CONFIRMED, OrderStatus.RECOVERED]),
            )
        ).all()
    )
    collected_total = 0
    for o in orders:
        existing_col = db.scalar(select(CollectionRecord).where(CollectionRecord.order_id == o.id))
        if existing_col is None:
            db.add(
                CollectionRecord(
                    order_id=o.id,
                    collected_quantity_grams=o.quantity_grams,
                    recorded_by_user_id=listing.farmer_id,
                    notes="[SIMULATED] Demo collection recorded",
                )
            )
            listing.reserved_quantity_grams = max(
                0, listing.reserved_quantity_grams - o.quantity_grams
            )
            listing.collected_quantity_grams += o.quantity_grams
            collected_total += o.quantity_grams
        if o.status == OrderStatus.CONFIRMED:
            o.status = OrderStatus.COLLECTED

    if listing.available_quantity_grams == 0 and listing.reserved_quantity_grams == 0:
        listing.status = ListingStatus.COMPLETED

    _record_demo_audit(
        db,
        admin=admin,
        action="DEMO_COLLECTION_RECORDED",
        resource_id=str(listing.id),
        detail=f"Recorded {collected_total}g collected across {len(orders)} orders",
    )
    db.commit()
    return {"listing_id": str(listing.id), "collected_grams": collected_total}


def reset_demo_only_data(db: Session, *, admin: User) -> dict[str, object]:
    """Safely delete ONLY is_simulated=True demo records; never touch production data."""
    sim_listing_ids = list(
        db.scalars(select(ProduceListing.id).where(ProduceListing.is_simulated.is_(True))).all()
    )
    if sim_listing_ids:
        sim_order_ids = list(
            db.scalars(select(Order.id).where(Order.listing_id.in_(sim_listing_ids))).all()
        )
        if sim_order_ids:
            db.execute(delete(CollectionRecord).where(CollectionRecord.order_id.in_(sim_order_ids)))
            db.execute(delete(DisputeCase).where(DisputeCase.order_id.in_(sim_order_ids)))
            db.execute(
                delete(BuyerReliabilityEvent).where(
                    BuyerReliabilityEvent.order_id.in_(sim_order_ids)
                )
            )
            db.execute(delete(Order).where(Order.id.in_(sim_order_ids)))

        sim_auction_ids = list(
            db.scalars(select(Auction.id).where(Auction.listing_id.in_(sim_listing_ids))).all()
        )
        if sim_auction_ids:
            db.execute(delete(Allocation).where(Allocation.auction_id.in_(sim_auction_ids)))
            db.execute(delete(AllocationRun).where(AllocationRun.auction_id.in_(sim_auction_ids)))
            db.execute(delete(BidRevision).where(BidRevision.auction_id.in_(sim_auction_ids)))
            db.execute(delete(Auction).where(Auction.id.in_(sim_auction_ids)))

        db.execute(delete(ProduceListing).where(ProduceListing.id.in_(sim_listing_ids)))

    _record_demo_audit(
        db,
        admin=admin,
        action="DEMO_DATA_RESET",
        resource_id="simulated_only",
        detail=f"Cleared {len(sim_listing_ids)} simulated listings (production untouched)",
    )
    db.commit()
    return {"cleared_simulated_listings": len(sim_listing_ids)}
