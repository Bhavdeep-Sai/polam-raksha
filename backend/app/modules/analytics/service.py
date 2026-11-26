from collections import defaultdict
from datetime import UTC, date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.allocation.models import Allocation, AllocationRun
from app.modules.analytics.schemas import (
    CropImpactPoint,
    DailyImpactPoint,
    ImpactAnalyticsResponse,
    ImpactMetricsSummary,
)
from app.modules.auctions.models import Auction
from app.modules.listings.models import CropCatalog, ProduceListing
from app.modules.orders.models import CollectionRecord, Order, OrderStatus
from app.shared.time import IST_TIMEZONE, to_ist


def _ist_date_bounds_to_utc(
    start_date: date | None, end_date: date | None
) -> tuple[datetime | None, datetime | None]:
    start_utc = (
        datetime.combine(start_date, time.min, tzinfo=IST_TIMEZONE).astimezone(UTC)
        if start_date is not None
        else None
    )
    end_utc = (
        datetime.combine(end_date, time.max, tzinfo=IST_TIMEZONE).astimezone(UTC)
        if end_date is not None
        else None
    )
    return start_utc, end_utc


def _compute_summary(
    db: Session,
    *,
    is_simulated: bool,
    start_utc: datetime | None,
    end_utc: datetime | None,
    crop_code: str | None,
    location: str | None,
) -> tuple[ImpactMetricsSummary, list[ProduceListing], list[Order], dict[str, CropCatalog]]:
    crops = {str(c.id): c for c in db.scalars(select(CropCatalog)).all()}
    target_crop_id: str | None = None
    if crop_code:
        for cid, c in crops.items():
            if c.code.upper() == crop_code.upper():
                target_crop_id = cid
                break

    listing_stmt = select(ProduceListing).where(ProduceListing.is_simulated.is_(is_simulated))
    if start_utc is not None:
        listing_stmt = listing_stmt.where(ProduceListing.created_at >= start_utc)
    if end_utc is not None:
        listing_stmt = listing_stmt.where(ProduceListing.created_at <= end_utc)
    if target_crop_id is not None:
        listing_stmt = listing_stmt.where(ProduceListing.crop_id == crops[target_crop_id].id)
    elif crop_code:
        # Non-existent crop code -> empty result
        listing_stmt = listing_stmt.where(ProduceListing.id.is_(None))
    if location:
        listing_stmt = listing_stmt.where(
            ProduceListing.approx_location_label.ilike(f"%{location.strip()}%")
        )

    listings = list(db.scalars(listing_stmt).all())
    listing_map = {item.id: item for item in listings}
    listing_ids = list(listing_map.keys())

    listed_grams = sum(item.total_quantity_grams for item in listings)
    unmatched_grams = sum(item.available_quantity_grams for item in listings)

    if not listing_ids:
        empty = ImpactMetricsSummary(
            is_simulated=is_simulated,
            dataset_label="Simulated Demo Metrics" if is_simulated else "Production Metrics",
            produce_listed_grams=0,
            produce_allocated_grams=0,
            produce_confirmed_grams=0,
            produce_collected_grams=0,
            surplus_produce_collected_grams=0,
            rescued_from_waste_grams=0,
            unmatched_produce_grams=0,
            cancelled_quantity_grams=0,
            recovered_after_cancellation_grams=0,
            gross_transaction_value_paise=0,
            estimated_net_sales_revenue_paise=0,
            reported_payment_received_paise=0,
            average_buyer_matching_time_seconds=None,
            buyer_completion_rate_percent=None,
            has_data=False,
            methodology_note=(
                "Allocated produce is never counted as collected or rescued. "
                "Only recovered/urgent collected produce with evidence is "
                "classified as rescued from waste."
            ),
            baseline_note=(
                "Additional farmer income is not claimed because no verified "
                "counterfactual baseline exists."
            ),
        )
        return empty, listings, [], crops

    # Allocations tied to matching listings via auctions
    alloc_rows = db.scalars(
        select(Allocation)
        .join(Auction, Allocation.auction_id == Auction.id)
        .join(AllocationRun, Allocation.allocation_run_id == AllocationRun.id)
        .where(
            Auction.listing_id.in_(listing_ids),
            AllocationRun.is_approved.is_(True),
        )
    ).all()
    allocated_grams = sum(a.allocated_quantity_grams for a in alloc_rows)

    orders = list(
        db.scalars(
            select(Order).where(
                Order.listing_id.in_(listing_ids),
                Order.is_simulated.is_(is_simulated),
            )
        ).all()
    )
    order_ids = [o.id for o in orders]
    collections_by_order: dict[object, CollectionRecord] = {}
    if order_ids:
        for col in db.scalars(
            select(CollectionRecord).where(CollectionRecord.order_id.in_(order_ids))
        ).all():
            collections_by_order[col.order_id] = col

    confirmed_grams = 0
    collected_grams = 0
    rescued_grams = 0
    surplus_collected_grams = 0
    cancelled_grams = 0
    recovered_grams = 0
    gross_paise = 0
    net_paise = 0
    reported_payment_paise = 0

    matching_durations: list[float] = []
    completed_order_count = 0
    terminal_order_count = 0

    for order in orders:
        listing = listing_map.get(order.listing_id)
        if listing is not None:
            o_ts = (
                order.created_at.replace(tzinfo=UTC)
                if order.created_at.tzinfo is None
                else order.created_at
            )
            l_ts = (
                listing.created_at.replace(tzinfo=UTC)
                if listing.created_at.tzinfo is None
                else listing.created_at
            )
            matching_durations.append(max(0.0, (o_ts - l_ts).total_seconds()))

        if order.status in {
            OrderStatus.CONFIRMED,
            OrderStatus.IN_TRANSIT,
            OrderStatus.COLLECTED,
            OrderStatus.RECOVERED,
        }:
            confirmed_grams += order.quantity_grams

        if order.status == OrderStatus.CANCELLED_BY_BUYER:
            cancelled_grams += order.quantity_grams
            terminal_order_count += 1
            continue

        if order.status == OrderStatus.EXPIRED:
            terminal_order_count += 1
            continue

        if order.status == OrderStatus.RECOVERED:
            recovered_grams += order.quantity_grams

        col_rec = collections_by_order.get(order.id)
        if order.status in {OrderStatus.COLLECTED, OrderStatus.RECOVERED} and col_rec is not None:
            completed_order_count += 1
            terminal_order_count += 1
            qty = col_rec.collected_quantity_grams
            collected_grams += qty
            gross_paise += order.total_amount_paise
            net_paise += max(0, order.total_amount_paise - order.transport_cost_paise)
            reported_payment_paise += order.total_amount_paise

            # Evidence-based waste rescue check
            at_risk_evidence = order.status == OrderStatus.RECOVERED or (
                listing is not None
                and listing.urgency_option in {"WITHIN_2H", "WITHIN_6H"}
            )
            if at_risk_evidence:
                rescued_grams += qty
            else:
                surplus_collected_grams += qty

    avg_match_sec = (
        int(round(sum(matching_durations) / len(matching_durations)))
        if matching_durations
        else None
    )
    completion_rate = (
        round((completed_order_count / terminal_order_count) * 100.0, 2)
        if terminal_order_count > 0
        else None
    )

    summary = ImpactMetricsSummary(
        is_simulated=is_simulated,
        dataset_label="Simulated Demo Metrics" if is_simulated else "Production Metrics",
        produce_listed_grams=listed_grams,
        produce_allocated_grams=allocated_grams,
        produce_confirmed_grams=confirmed_grams,
        produce_collected_grams=collected_grams,
        surplus_produce_collected_grams=surplus_collected_grams,
        rescued_from_waste_grams=rescued_grams,
        unmatched_produce_grams=unmatched_grams,
        cancelled_quantity_grams=cancelled_grams,
        recovered_after_cancellation_grams=recovered_grams,
        gross_transaction_value_paise=gross_paise,
        estimated_net_sales_revenue_paise=net_paise,
        reported_payment_received_paise=reported_payment_paise,
        average_buyer_matching_time_seconds=avg_match_sec,
        buyer_completion_rate_percent=completion_rate,
        has_data=len(listings) > 0,
        methodology_note=(
            "Allocated produce is never counted as collected or rescued. "
            "Only recovered/urgent collected produce with evidence is "
            "classified as rescued from waste."
        ),
        baseline_note=(
            "Additional farmer income is not claimed because no verified "
            "counterfactual baseline exists."
        ),
    )
    return summary, listings, orders, crops


def get_impact_analytics(
    db: Session,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    crop_code: str | None = None,
    location: str | None = None,
    include_simulated: bool = False,
) -> ImpactAnalyticsResponse:
    start_utc, end_utc = _ist_date_bounds_to_utc(start_date, end_date)
    prod_summary, prod_listings, prod_orders, crops = _compute_summary(
        db,
        is_simulated=False,
        start_utc=start_utc,
        end_utc=end_utc,
        crop_code=crop_code,
        location=location,
    )

    demo_summary: ImpactMetricsSummary | None = None
    if include_simulated:
        demo_summary, _, _, _ = _compute_summary(
            db,
            is_simulated=True,
            start_utc=start_utc,
            end_utc=end_utc,
            crop_code=crop_code,
            location=location,
        )

    # Build daily series in IST from production listings & orders
    daily_listed: dict[str, int] = defaultdict(int)
    daily_allocated: dict[str, int] = defaultdict(int)
    daily_collected: dict[str, int] = defaultdict(int)
    daily_cancelled: dict[str, int] = defaultdict(int)
    crop_listed: dict[str, int] = defaultdict(int)
    crop_collected: dict[str, int] = defaultdict(int)
    listing_crop: dict[object, str] = {}

    for item in prod_listings:
        day_str = to_ist(item.created_at).date().isoformat()
        daily_listed[day_str] += item.total_quantity_grams
        cid = str(item.crop_id)
        listing_crop[item.id] = cid
        crop_listed[cid] += item.total_quantity_grams

    for o in prod_orders:
        day_str = to_ist(o.created_at).date().isoformat()
        if o.status == OrderStatus.CANCELLED_BY_BUYER:
            daily_cancelled[day_str] += o.quantity_grams
        else:
            daily_allocated[day_str] += o.quantity_grams
            if o.status in {OrderStatus.COLLECTED, OrderStatus.RECOVERED}:
                daily_collected[day_str] += o.quantity_grams
                cid = listing_crop.get(o.listing_id, "")
                if cid:
                    crop_collected[cid] += o.quantity_grams

    all_days = sorted(
        set(daily_listed.keys())
        | set(daily_allocated.keys())
        | set(daily_collected.keys())
        | set(daily_cancelled.keys())
    )
    daily_series = [
        DailyImpactPoint(
            date_ist=d,
            listed_kg=round(daily_listed[d] / 1000.0, 2),
            allocated_kg=round(daily_allocated[d] / 1000.0, 2),
            collected_kg=round(daily_collected[d] / 1000.0, 2),
            cancelled_kg=round(daily_cancelled[d] / 1000.0, 2),
        )
        for d in all_days
    ]

    crop_breakdown = [
        CropImpactPoint(
            crop_code=crops[cid].code,
            crop_name_en=crops[cid].name_en,
            crop_name_te=crops[cid].name_te,
            listed_kg=round(crop_listed[cid] / 1000.0, 2),
            collected_kg=round(crop_collected[cid] / 1000.0, 2),
        )
        for cid in sorted(crop_listed.keys())
        if cid in crops
    ]

    return ImpactAnalyticsResponse(
        start_date=start_date,
        end_date=end_date,
        crop_code=crop_code,
        location=location,
        production=prod_summary,
        demo_simulated=demo_summary,
        daily_series=daily_series,
        crop_breakdown=crop_breakdown,
    )
