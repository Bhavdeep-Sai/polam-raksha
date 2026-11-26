import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.auctions.models import Auction, AuctionStatus, BidRevision
from app.modules.auctions.schemas import (
    AuctionDetailResponse,
    BidRevisionPublicResponse,
    PlaceBidRequest,
)
from app.modules.auth.service import record_audit_event
from app.modules.listings.models import ProduceListing
from app.modules.system.models import IdempotencyRecord, TransactionalOutboxEvent
from app.modules.users.models import BuyerProfile, User, UserRole
from app.shared.time import utc_now
from app.workers.jobs import reschedule_auction_close_job


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _buyer_alias(buyer_id: uuid.UUID) -> str:
    return f"Buyer #{str(buyer_id)[:6].upper()}"


def _to_public_bid(
    bid: BidRevision, *, current_user_id: uuid.UUID | None
) -> BidRevisionPublicResponse:
    return BidRevisionPublicResponse(
        id=bid.id,
        auction_id=bid.auction_id,
        buyer_alias=_buyer_alias(bid.buyer_id),
        is_own_bid=current_user_id == bid.buyer_id,
        revision_number=bid.revision_number,
        bid_price_paise_per_kg=bid.bid_price_paise_per_kg,
        requested_quantity_grams=bid.requested_quantity_grams,
        min_acceptable_grams=bid.min_acceptable_grams,
        estimated_collection_at=_ensure_utc(bid.estimated_collection_at),
        transport_responsibility=bid.transport_responsibility,
        estimated_transport_cost_paise=bid.estimated_transport_cost_paise,
        standby_until=_ensure_utc(bid.standby_until),
        is_active=bid.is_active,
        created_at=_ensure_utc(bid.created_at),
    )


def _build_auction_detail(
    db: Session,
    *,
    auction: Auction,
    listing: ProduceListing,
    current_user_id: uuid.UUID | None,
    soft_closed_triggered: bool = False,
) -> AuctionDetailResponse:
    now = utc_now()
    active_bids = db.scalars(
        select(BidRevision)
        .where(
            BidRevision.auction_id == auction.id,
            BidRevision.is_active.is_(True),
        )
        .order_by(BidRevision.bid_price_paise_per_kg.desc(), BidRevision.created_at.asc())
    ).all()

    my_revisions: list[BidRevision] = []
    if current_user_id is not None:
        my_revisions = list(
            db.scalars(
                select(BidRevision)
                .where(
                    BidRevision.auction_id == auction.id,
                    BidRevision.buyer_id == current_user_id,
                )
                .order_by(BidRevision.revision_number.desc())
            ).all()
        )

    highest_price = active_bids[0].bid_price_paise_per_kg if active_bids else None

    return AuctionDetailResponse(
        id=auction.id,
        listing_id=auction.listing_id,
        status=auction.status,
        min_bid_paise_per_kg=auction.min_bid_paise_per_kg,
        min_increment_paise_per_kg=auction.min_increment_paise_per_kg,
        starts_at=_ensure_utc(auction.starts_at),
        ends_at=_ensure_utc(auction.ends_at),
        hard_close_at=_ensure_utc(auction.hard_close_at),
        soft_close_trigger_seconds=auction.soft_close_trigger_seconds,
        soft_close_extension_seconds=auction.soft_close_extension_seconds,
        soft_close_max_extension_seconds=auction.soft_close_max_extension_seconds,
        soft_close_extended_seconds=auction.soft_close_extended_seconds,
        version=auction.version,
        server_time_utc=now,
        available_quantity_grams=listing.available_quantity_grams,
        spoilage_deadline_at=_ensure_utc(listing.spoilage_deadline_at),
        approx_location_label=listing.approx_location_label,
        is_direct_offer_mode=listing.is_direct_offer_mode,
        highest_unit_price_paise_per_kg=highest_price,
        soft_closed_triggered=soft_closed_triggered,
        active_offers=[_to_public_bid(b, current_user_id=current_user_id) for b in active_bids],
        my_bid_revisions=[
            _to_public_bid(b, current_user_id=current_user_id) for b in my_revisions
        ],
    )


def get_auction_detail(
    db: Session,
    *,
    auction_id: uuid.UUID,
    current_user: User | None = None,
) -> AuctionDetailResponse:
    auction = db.scalar(select(Auction).where(Auction.id == auction_id))
    if auction is None:
        raise AppError(
            code="auction_not_found",
            message="Auction not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    listing = db.scalar(select(ProduceListing).where(ProduceListing.id == auction.listing_id))
    if listing is None:
        raise AppError(
            code="listing_not_found",
            message="Produce listing not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return _build_auction_detail(
        db,
        auction=auction,
        listing=listing,
        current_user_id=current_user.id if current_user else None,
    )


def list_open_auctions(
    db: Session,
    *,
    current_user: User | None = None,
) -> list[AuctionDetailResponse]:
    auctions = db.scalars(
        select(Auction)
        .where(Auction.status.in_([AuctionStatus.OPEN, AuctionStatus.CLOSING]))
        .order_by(Auction.ends_at.asc())
    ).all()
    results: list[AuctionDetailResponse] = []
    for auction in auctions:
        listing = db.scalar(select(ProduceListing).where(ProduceListing.id == auction.listing_id))
        if listing is not None:
            results.append(
                _build_auction_detail(
                    db,
                    auction=auction,
                    listing=listing,
                    current_user_id=current_user.id if current_user else None,
                )
            )
    return results


def place_or_revise_bid(
    db: Session,
    *,
    auction_id: uuid.UUID,
    buyer: User,
    payload: PlaceBidRequest,
    ip_address: str | None = None,
) -> AuctionDetailResponse:
    """Validate and record an immutable bid revision inside a locked DB transaction."""
    if buyer.role != UserRole.BUYER or not buyer.is_active:
        raise AppError(
            code="buyer_not_eligible",
            message="Only active buyers can place bids",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    endpoint_key = f"/auctions/{auction_id}/bids"
    request_hash = hashlib.sha256(
        json.dumps(payload.model_dump(mode="json"), sort_keys=True).encode("utf-8")
    ).hexdigest()

    existing_idem = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.idempotency_key == payload.idempotency_key,
            IdempotencyRecord.actor_user_id == buyer.id,
            IdempotencyRecord.endpoint == endpoint_key,
        )
    )
    if existing_idem is not None:
        if existing_idem.request_hash != request_hash:
            raise AppError(
                code="idempotency_key_conflict",
                message="Idempotency key was already used with a different bid payload",
                status_code=status.HTTP_409_CONFLICT,
            )
        return AuctionDetailResponse.model_validate(existing_idem.response_body_json)

    buyer_profile = db.scalar(select(BuyerProfile).where(BuyerProfile.user_id == buyer.id))
    if buyer_profile is not None and buyer_profile.reliability_score < 20:
        raise AppError(
            code="buyer_restricted",
            message="Buyer account is temporarily restricted due to low reliability score",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    # Lock Auction and ProduceListing in deterministic order to prevent races/overselling.
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

    now = utc_now()
    ends_at = _ensure_utc(auction.ends_at)
    hard_close_at = _ensure_utc(auction.hard_close_at)
    spoilage_deadline = _ensure_utc(listing.spoilage_deadline_at)

    if auction.status not in {AuctionStatus.OPEN, AuctionStatus.CLOSING} or now >= ends_at:
        raise AppError(
            code="auction_closed",
            message="Auction is closed or past its bidding deadline",
            status_code=status.HTTP_409_CONFLICT,
        )

    if payload.bid_price_paise_per_kg < auction.min_bid_paise_per_kg:
        raise AppError(
            code="bid_below_reserve",
            message="Bid price must meet or exceed the farmer's reserve price",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    if payload.requested_quantity_grams > listing.available_quantity_grams:
        raise AppError(
            code="quantity_exceeds_available",
            message="Requested quantity exceeds available listing inventory",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    est_collection = _ensure_utc(payload.estimated_collection_at)
    standby_until = _ensure_utc(payload.standby_until)
    if est_collection <= now or est_collection > spoilage_deadline:
        raise AppError(
            code="infeasible_collection_time",
            message="Estimated collection time must be before the listing spoilage deadline",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    if standby_until <= now or standby_until > spoilage_deadline:
        raise AppError(
            code="invalid_standby_deadline",
            message="Standby availability deadline must be before the spoilage deadline",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    active_bids = db.scalars(
        select(BidRevision).where(
            BidRevision.auction_id == auction.id,
            BidRevision.is_active.is_(True),
        )
    ).all()

    previous_own = next((b for b in active_bids if b.buyer_id == buyer.id), None)
    previous_highest_price = max(
        (b.bid_price_paise_per_kg for b in active_bids),
        default=None,
    )
    competing_full_lot_max = max(
        (
            b.bid_price_paise_per_kg
            for b in active_bids
            if b.buyer_id != buyer.id
            and b.requested_quantity_grams == listing.available_quantity_grams
        ),
        default=None,
    )

    is_full_lot = payload.requested_quantity_grams == listing.available_quantity_grams
    if is_full_lot and competing_full_lot_max is not None:
        required_min = competing_full_lot_max + auction.min_increment_paise_per_kg
        if payload.bid_price_paise_per_kg < required_min:
            raise AppError(
                code="bid_below_minimum_increment",
                message=(
                    f"Full-lot bids must exceed the current competing full-lot offer by at "
                    f"least {auction.min_increment_paise_per_kg} paise/kg"
                ),
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            )

    if previous_own is not None:
        price_improved = (
            payload.bid_price_paise_per_kg
            >= previous_own.bid_price_paise_per_kg + auction.min_increment_paise_per_kg
        )
        partial_qty_improved = (
            not is_full_lot
            and payload.bid_price_paise_per_kg >= previous_own.bid_price_paise_per_kg
            and (
                payload.requested_quantity_grams > previous_own.requested_quantity_grams
                or payload.min_acceptable_grams < previous_own.min_acceptable_grams
            )
        )
        if not (price_improved or partial_qty_improved):
            raise AppError(
                code="bid_must_improve",
                message="Revised offer must improve price or partial-quantity feasibility",
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            )
        previous_own.is_active = False

    next_revision = (previous_own.revision_number + 1) if previous_own is not None else 1
    new_bid = BidRevision(
        auction_id=auction.id,
        buyer_id=buyer.id,
        revision_number=next_revision,
        bid_price_paise_per_kg=payload.bid_price_paise_per_kg,
        requested_quantity_grams=payload.requested_quantity_grams,
        min_acceptable_grams=payload.min_acceptable_grams,
        estimated_collection_at=est_collection,
        transport_responsibility=payload.transport_responsibility,
        estimated_transport_cost_paise=payload.estimated_transport_cost_paise,
        standby_until=standby_until,
        idempotency_key=payload.idempotency_key,
        is_active=True,
    )
    db.add(new_bid)
    db.flush()

    # Soft-close evaluation: extend only for qualifying competitive improvements.
    qualifying_improvement = (
        previous_highest_price is None
        or payload.bid_price_paise_per_kg
        >= previous_highest_price + auction.min_increment_paise_per_kg
    )
    soft_closed_triggered = False
    in_trigger_window = (ends_at - now) <= timedelta(seconds=auction.soft_close_trigger_seconds)

    if qualifying_improvement and in_trigger_window:
        remaining_cap = (
            auction.soft_close_max_extension_seconds - auction.soft_close_extended_seconds
        )
        if remaining_cap > 0 and ends_at < hard_close_at:
            max_allowed_end = min(hard_close_at, ends_at + timedelta(seconds=remaining_cap))
            proposed_end = min(
                ends_at + timedelta(seconds=auction.soft_close_extension_seconds),
                max_allowed_end,
            )
            if proposed_end > ends_at:
                added_seconds = int((proposed_end - ends_at).total_seconds())
                auction.ends_at = proposed_end
                auction.soft_close_extended_seconds += added_seconds
                auction.status = AuctionStatus.CLOSING
                reschedule_auction_close_job(db, auction_id=auction.id, new_run_at=proposed_end)
                soft_closed_triggered = True

    auction.version += 1

    db.add(
        TransactionalOutboxEvent(
            aggregate_type="auction",
            aggregate_id=auction.id,
            event_type="BID_PLACED",
            payload_json={
                "auction_id": str(auction.id),
                "entity_version": auction.version,
                "buyer_alias": _buyer_alias(buyer.id),
                "bid_price_paise_per_kg": new_bid.bid_price_paise_per_kg,
                "requested_quantity_grams": new_bid.requested_quantity_grams,
                "ends_at": _ensure_utc(auction.ends_at).isoformat(),
                "status": auction.status.value,
            },
        )
    )
    if soft_closed_triggered:
        db.add(
            TransactionalOutboxEvent(
                aggregate_type="auction",
                aggregate_id=auction.id,
                event_type="AUCTION_SOFT_CLOSED",
                payload_json={
                    "auction_id": str(auction.id),
                    "entity_version": auction.version,
                    "ends_at": _ensure_utc(auction.ends_at).isoformat(),
                    "soft_close_extended_seconds": auction.soft_close_extended_seconds,
                },
            )
        )

    record_audit_event(
        db,
        actor_user_id=buyer.id,
        action="BID_REVISION_PLACED",
        resource_type="bid_revision",
        resource_id=str(new_bid.id),
        metadata={
            "auction_id": str(auction.id),
            "revision_number": next_revision,
            "bid_price_paise_per_kg": new_bid.bid_price_paise_per_kg,
            "soft_closed_triggered": soft_closed_triggered,
        },
        ip_address=ip_address,
    )

    detail = _build_auction_detail(
        db,
        auction=auction,
        listing=listing,
        current_user_id=buyer.id,
        soft_closed_triggered=soft_closed_triggered,
    )

    db.add(
        IdempotencyRecord(
            idempotency_key=payload.idempotency_key,
            actor_user_id=buyer.id,
            endpoint=endpoint_key,
            request_hash=request_hash,
            response_status=status.HTTP_201_CREATED,
            response_body_json=detail.model_dump(mode="json"),
        )
    )

    db.commit()
    return detail

