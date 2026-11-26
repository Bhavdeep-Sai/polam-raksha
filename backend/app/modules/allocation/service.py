import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.allocation.models import Allocation, AllocationRun, AllocationRunStatus
from app.modules.allocation.schemas import (
    AllocationItemResponse,
    AllocationRunResponse,
    RunAllocationRequest,
)
from app.modules.allocation.solver import (
    AllocationInput,
    BuyerOfferInput,
    SolverStatus,
    solve_allocation,
)
from app.modules.auctions.models import Auction, AuctionStatus, BidRevision
from app.modules.auth.dependencies import authorize_farmer_access
from app.modules.auth.service import record_audit_event
from app.modules.listings.models import ListingStatus, ProduceListing
from app.modules.orders.models import Order, OrderStatus
from app.modules.system.models import TransactionalOutboxEvent
from app.modules.users.models import BuyerProfile, User, UserRole
from app.shared.time import utc_now


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _to_run_response(
    run: AllocationRun, allocations: list[Allocation]
) -> AllocationRunResponse:
    return AllocationRunResponse(
        id=run.id,
        auction_id=run.auction_id,
        status=run.status,
        solver_status=run.solver_status,
        algorithm_version=run.algorithm_version,
        strategy=run.strategy,
        gross_revenue_paise=run.gross_revenue_paise,
        transportation_cost_paise=run.transportation_cost_paise,
        estimated_net_revenue_paise=run.estimated_net_revenue_paise,
        unallocated_quantity_grams=run.unallocated_quantity_grams,
        execution_time_ms=run.execution_time_ms,
        is_approved=run.is_approved,
        approved_at=run.approved_at,
        explanations=list(run.explanations_json),
        allocations=[
            AllocationItemResponse(
                id=a.id,
                buyer_id=a.buyer_id,
                allocated_quantity_grams=a.allocated_quantity_grams,
                unit_price_paise_per_kg=a.unit_price_paise_per_kg,
                transport_cost_paise=a.transport_cost_paise,
            )
            for a in allocations
        ],
        created_at=run.created_at,
    )


def _commit_allocation_in_tx(
    db: Session,
    *,
    run: AllocationRun,
    allocations: list[Allocation],
    listing: ProduceListing,
    auction: Auction,
    actor_user_id: uuid.UUID,
    now: datetime,
    ip_address: str | None = None,
) -> None:
    """Revalidate listing inventory and reserve allocated quantities + create Orders."""
    if run.is_approved:
        raise AppError(
            code="allocation_already_approved",
            message="Allocation run has already been approved and committed",
            status_code=status.HTTP_409_CONFLICT,
        )

    if not allocations:
        raise AppError(
            code="empty_allocation",
            message="Cannot approve an allocation run with no selected buyers",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    spoilage_deadline = _ensure_utc(listing.spoilage_deadline_at)
    if spoilage_deadline <= now:
        raise AppError(
            code="listing_expired",
            message="Cannot commit allocation after the listing collection deadline",
            status_code=status.HTTP_409_CONFLICT,
        )

    total_allocated = sum(a.allocated_quantity_grams for a in allocations)
    if total_allocated > listing.available_quantity_grams:
        raise AppError(
            code="stale_allocation_inventory",
            message="Available inventory has changed and is insufficient for this allocation run",
            status_code=status.HTTP_409_CONFLICT,
        )

    listing.available_quantity_grams -= total_allocated
    listing.reserved_quantity_grams += total_allocated
    listing.status = (
        ListingStatus.FULLY_ALLOCATED
        if listing.available_quantity_grams == 0
        else ListingStatus.PARTIALLY_ALLOCATED
    )

    if auction.status in {AuctionStatus.OPEN, AuctionStatus.CLOSING}:
        auction.status = AuctionStatus.CLOSED
        auction.closed_at = now
        auction.version += 1

    for alloc in allocations:
        total_amount = round(
            (alloc.allocated_quantity_grams / 1000) * alloc.unit_price_paise_per_kg
        )
        db.add(
            Order(
                allocation_id=alloc.id,
                listing_id=listing.id,
                farmer_id=listing.farmer_id,
                buyer_id=alloc.buyer_id,
                status=OrderStatus.PENDING_CONFIRMATION,
                quantity_grams=alloc.allocated_quantity_grams,
                total_amount_paise=total_amount,
                transport_cost_paise=alloc.transport_cost_paise,
                pickup_deadline_at=listing.spoilage_deadline_at,
                is_simulated=listing.is_simulated,
            )
        )

    run.is_approved = True
    run.approved_at = now

    db.add(
        TransactionalOutboxEvent(
            aggregate_type="auction",
            aggregate_id=auction.id,
            event_type="ALLOCATION_COMMITTED",
            payload_json={
                "auction_id": str(auction.id),
                "allocation_run_id": str(run.id),
                "total_allocated_grams": total_allocated,
                "entity_version": auction.version,
            },
        )
    )
    record_audit_event(
        db,
        actor_user_id=actor_user_id,
        acting_as_farmer_id=listing.farmer_id if actor_user_id != listing.farmer_id else None,
        action="ALLOCATION_APPROVED_AND_COMMITTED",
        resource_type="allocation_run",
        resource_id=str(run.id),
        metadata={"total_allocated_grams": total_allocated},
        ip_address=ip_address,
    )


def run_allocation_for_auction(
    db: Session,
    *,
    auction_id: uuid.UUID,
    payload: RunAllocationRequest,
    current_user: User,
    ip_address: str | None = None,
) -> AllocationRunResponse:
    """Execute OR-Tools CP-SAT allocation on latest eligible offers and persist snapshot."""
    auction = db.scalar(select(Auction).where(Auction.id == auction_id).with_for_update())
    if auction is None:
        raise AppError(
            code="auction_not_found",
            message="Auction not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    listing = db.scalar(
        select(ProduceListing)
        .where(ProduceListing.id == auction.listing_id)
        .with_for_update()
    )
    if listing is None:
        raise AppError(
            code="listing_not_found",
            message="Produce listing not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if current_user.role != UserRole.ADMIN:
        authorize_farmer_access(farmer_id=listing.farmer_id, current_user=current_user, db=db)

    active_bids = db.scalars(
        select(BidRevision).where(
            BidRevision.auction_id == auction.id,
            BidRevision.is_active.is_(True),
        )
    ).all()

    offers: list[BuyerOfferInput] = []
    for bid in active_bids:
        profile = db.scalar(select(BuyerProfile).where(BuyerProfile.user_id == bid.buyer_id))
        reliability = profile.reliability_score if profile else 100
        farmer_var_transport = (
            round(bid.estimated_transport_cost_paise / max(1, bid.requested_quantity_grams / 1000))
            if bid.transport_responsibility == "FARMER_DELIVERY"
            else 0
        )
        offers.append(
            BuyerOfferInput(
                buyer_id=str(bid.buyer_id),
                unit_price_paise_per_kg=bid.bid_price_paise_per_kg,
                min_quantity_grams=bid.min_acceptable_grams,
                max_quantity_grams=bid.requested_quantity_grams,
                estimated_collection_at=bid.estimated_collection_at,
                farmer_paid_variable_transport_paise_per_kg=farmer_var_transport,
                farmer_paid_fixed_pickup_cost_paise=0,
                reliability_score=reliability,
                is_eligible=True,
            )
        )

    committed_grams = listing.reserved_quantity_grams + listing.collected_quantity_grams
    solver_input = AllocationInput(
        available_quantity_grams=listing.available_quantity_grams,
        committed_quantity_grams=committed_grams,
        reserve_price_paise_per_kg=listing.floor_price_paise_per_kg,
        hard_collection_deadline=listing.spoilage_deadline_at,
        strategy=payload.strategy,
        min_net_revenue_paise=payload.min_net_revenue_paise,
        time_limit_seconds=payload.time_limit_seconds,
        offers=offers,
    )

    output = solve_allocation(solver_input)
    now = utc_now()

    run_status = (
        AllocationRunStatus.SOLVED
        if output.solver_status in {SolverStatus.OPTIMAL, SolverStatus.FEASIBLE}
        else AllocationRunStatus.INFEASIBLE
        if output.solver_status == SolverStatus.INFEASIBLE
        else AllocationRunStatus.FAILED
    )

    snapshot: dict[str, Any] = {
        "available_quantity_grams": solver_input.available_quantity_grams,
        "committed_quantity_grams": solver_input.committed_quantity_grams,
        "reserve_price_paise_per_kg": solver_input.reserve_price_paise_per_kg,
        "hard_collection_deadline": _ensure_utc(solver_input.hard_collection_deadline).isoformat(),
        "strategy": solver_input.strategy.value,
        "offer_count": len(offers),
    }

    run = AllocationRun(
        auction_id=auction.id,
        status=run_status,
        solver_status=output.solver_status.value,
        algorithm_version=output.algorithm_version,
        strategy=payload.strategy.value,
        input_snapshot_json=snapshot,
        explanations_json=output.explanations,
        gross_revenue_paise=output.gross_revenue_paise,
        transportation_cost_paise=output.transportation_cost_paise,
        estimated_net_revenue_paise=output.estimated_net_revenue_paise,
        unallocated_quantity_grams=output.unallocated_quantity_grams,
        execution_time_ms=output.execution_time_ms,
        objective_value_paise=output.estimated_net_revenue_paise,
        completed_at=now,
    )
    db.add(run)
    db.flush()

    alloc_rows: list[Allocation] = []
    for item in output.selected_buyers:
        alloc = Allocation(
            allocation_run_id=run.id,
            auction_id=auction.id,
            buyer_id=uuid.UUID(item.buyer_id),
            allocated_quantity_grams=item.allocated_quantity_grams,
            unit_price_paise_per_kg=item.unit_price_paise_per_kg,
            transport_cost_paise=item.transportation_cost_paise,
        )
        db.add(alloc)
        alloc_rows.append(alloc)
    db.flush()

    if listing.auto_allocate_approved and alloc_rows:
        _commit_allocation_in_tx(
            db,
            run=run,
            allocations=alloc_rows,
            listing=listing,
            auction=auction,
            actor_user_id=current_user.id,
            now=now,
            ip_address=ip_address,
        )

    db.commit()
    return _to_run_response(run, alloc_rows)


def approve_allocation_run(
    db: Session,
    *,
    run_id: uuid.UUID,
    current_user: User,
    ip_address: str | None = None,
) -> AllocationRunResponse:
    run = db.scalar(select(AllocationRun).where(AllocationRun.id == run_id).with_for_update())
    if run is None:
        raise AppError(
            code="allocation_run_not_found",
            message="Allocation run not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    auction = db.scalar(select(Auction).where(Auction.id == run.auction_id).with_for_update())
    if auction is None:
        raise AppError(
            code="auction_not_found",
            message="Auction not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    listing = db.scalar(
        select(ProduceListing)
        .where(ProduceListing.id == auction.listing_id)
        .with_for_update()
    )
    if listing is None:
        raise AppError(
            code="listing_not_found",
            message="Produce listing not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    authorize_farmer_access(farmer_id=listing.farmer_id, current_user=current_user, db=db)

    alloc_rows = list(
        db.scalars(select(Allocation).where(Allocation.allocation_run_id == run.id)).all()
    )
    _commit_allocation_in_tx(
        db,
        run=run,
        allocations=alloc_rows,
        listing=listing,
        auction=auction,
        actor_user_id=current_user.id,
        now=utc_now(),
        ip_address=ip_address,
    )
    db.commit()
    return _to_run_response(run, alloc_rows)


def _hydrate_allocation_runs(db: Session, runs: list[AllocationRun]) -> list[AllocationRunResponse]:
    if not runs:
        return []
    run_ids = [r.id for r in runs]
    allocs = db.scalars(
        select(Allocation).where(Allocation.allocation_run_id.in_(run_ids))
    ).all()
    by_run: dict[uuid.UUID, list[Allocation]] = {rid: [] for rid in run_ids}
    for alloc in allocs:
        by_run[alloc.allocation_run_id].append(alloc)
    return [_to_run_response(run, by_run[run.id]) for run in runs]


def list_runs_for_auction(
    db: Session,
    *,
    auction_id: uuid.UUID,
) -> list[AllocationRunResponse]:
    runs = list(
        db.scalars(
            select(AllocationRun)
            .where(AllocationRun.auction_id == auction_id)
            .order_by(AllocationRun.created_at.desc())
        ).all()
    )
    return _hydrate_allocation_runs(db, runs)


def list_all_allocation_runs(db: Session, *, limit: int = 30) -> list[AllocationRunResponse]:
    runs = list(
        db.scalars(
            select(AllocationRun).order_by(AllocationRun.created_at.desc()).limit(limit)
        ).all()
    )
    return _hydrate_allocation_runs(db, runs)

