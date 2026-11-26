import uuid
from datetime import UTC

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.auctions.models import Auction, AuctionStatus
from app.modules.auth.dependencies import authorize_farmer_access
from app.modules.auth.service import record_audit_event
from app.modules.listings.deadline_policy import compute_deadline_schedule
from app.modules.listings.models import CropCatalog, ListingStatus, ProduceListing
from app.modules.listings.schemas import (
    CreateListingRequest,
    CropCatalogItem,
    FarmerListingDetailResponse,
    PublicListingResponse,
    QuantityUnit,
    UpdateListingRequest,
)
from app.modules.users.models import User, UserRole
from app.shared.time import utc_now
from app.workers.jobs import enqueue_job

ALLOWED_LISTING_TRANSITIONS: dict[ListingStatus, set[ListingStatus]] = {
    ListingStatus.DRAFT: {ListingStatus.ACTIVE, ListingStatus.CANCELLED},
    ListingStatus.ACTIVE: {
        ListingStatus.PARTIALLY_ALLOCATED,
        ListingStatus.FULLY_ALLOCATED,
        ListingStatus.ALLOCATED,
        ListingStatus.CANCELLED,
        ListingStatus.EXPIRED,
    },
    ListingStatus.PARTIALLY_ALLOCATED: {
        ListingStatus.FULLY_ALLOCATED,
        ListingStatus.COMPLETED,
        ListingStatus.CANCELLED,
        ListingStatus.EXPIRED,
    },
    ListingStatus.FULLY_ALLOCATED: {
        ListingStatus.COMPLETED,
        ListingStatus.CANCELLED,
    },
    ListingStatus.ALLOCATED: {ListingStatus.COMPLETED, ListingStatus.CANCELLED},
    ListingStatus.COMPLETED: set(),
    ListingStatus.CANCELLED: set(),
    ListingStatus.EXPIRED: set(),
}


def convert_to_grams(
    *, quantity_value: float | None, unit: QuantityUnit, raw_grams: int | None
) -> int:
    """Convert caller-supplied quantity and unit into integer grams."""
    if raw_grams is not None:
        return raw_grams
    if quantity_value is None or quantity_value <= 0:
        raise AppError(
            code="invalid_quantity",
            message="A positive quantity_value or total_quantity_grams is required",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    multiplier = {"GRAM": 1, "KG": 1000, "QUINTAL": 100_000}[unit]
    grams = round(quantity_value * multiplier)
    if grams <= 0:
        raise AppError(
            code="invalid_quantity",
            message="Converted quantity in grams must be positive",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    return grams


def to_public_listing(listing: ProduceListing) -> PublicListingResponse:
    return PublicListingResponse(
        id=listing.id,
        crop_id=listing.crop_id,
        status=listing.status,
        available_quantity_grams=listing.available_quantity_grams,
        floor_price_paise_per_kg=listing.floor_price_paise_per_kg,
        harvested_at=listing.harvested_at,
        spoilage_deadline_at=listing.spoilage_deadline_at,
        approx_location_label=listing.approx_location_label,
        approx_latitude=listing.approx_latitude,
        approx_longitude=listing.approx_longitude,
        quality_grade=listing.quality_grade,
        transport_responsibility=listing.transport_responsibility,
        urgency_option=listing.urgency_option,
        is_direct_offer_mode=listing.is_direct_offer_mode,
        is_simulated=listing.is_simulated,
    )


def to_farmer_listing_detail(
    listing: ProduceListing, auction: Auction | None
) -> FarmerListingDetailResponse:
    return FarmerListingDetailResponse(
        id=listing.id,
        crop_id=listing.crop_id,
        status=listing.status,
        available_quantity_grams=listing.available_quantity_grams,
        floor_price_paise_per_kg=listing.floor_price_paise_per_kg,
        harvested_at=listing.harvested_at,
        spoilage_deadline_at=listing.spoilage_deadline_at,
        approx_location_label=listing.approx_location_label,
        approx_latitude=listing.approx_latitude,
        approx_longitude=listing.approx_longitude,
        quality_grade=listing.quality_grade,
        transport_responsibility=listing.transport_responsibility,
        urgency_option=listing.urgency_option,
        is_direct_offer_mode=listing.is_direct_offer_mode,
        is_simulated=listing.is_simulated,
        farmer_id=listing.farmer_id,
        created_by_user_id=listing.created_by_user_id,
        total_quantity_grams=listing.total_quantity_grams,
        reserved_quantity_grams=listing.reserved_quantity_grams,
        collected_quantity_grams=listing.collected_quantity_grams,
        auto_allocate_approved=listing.auto_allocate_approved,
        bidding_initial_close_at=listing.bidding_initial_close_at,
        bidding_hard_close_at=listing.bidding_hard_close_at,
        farmer_approval_deadline_at=listing.farmer_approval_deadline_at,
        buyer_confirmation_deadline_at=listing.buyer_confirmation_deadline_at,
        recovery_deadline_at=listing.recovery_deadline_at,
        auction_id=auction.id if auction else None,
        auction_status=auction.status if auction else None,
    )


def list_active_crops(db: Session) -> list[CropCatalogItem]:
    rows = db.scalars(
        select(CropCatalog).where(CropCatalog.is_active.is_(True)).order_by(CropCatalog.name_en)
    ).all()
    return [
        CropCatalogItem(
            id=row.id,
            code=row.code,
            name_en=row.name_en,
            name_te=row.name_te,
            unit_label_en=row.unit_label_en,
            unit_label_te=row.unit_label_te,
            default_shelf_life_hours=row.default_shelf_life_hours,
        )
        for row in rows
    ]


def create_produce_listing(
    db: Session,
    *,
    payload: CreateListingRequest,
    current_user: User,
    ip_address: str | None = None,
) -> FarmerListingDetailResponse:
    """Create a produce listing and its linked auction using the shared deadline policy."""
    target_farmer_id = payload.farmer_id or current_user.id
    farmer = authorize_farmer_access(
        farmer_id=target_farmer_id,
        current_user=current_user,
        db=db,
    )

    if current_user.role == UserRole.OPERATOR and not payload.consent_confirmed:
        raise AppError(
            code="farmer_consent_required",
            message="Operator must confirm farmer consent before creating an assisted listing",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    total_grams = convert_to_grams(
        quantity_value=payload.quantity_value,
        unit=payload.quantity_unit,
        raw_grams=payload.total_quantity_grams,
    )

    now = utc_now()
    harvested_at = (
        payload.harvested_at.replace(tzinfo=UTC)
        if payload.harvested_at.tzinfo is None
        else payload.harvested_at.astimezone(UTC)
    )
    urgency_option = payload.urgency_option
    custom_deadline = payload.spoilage_deadline_at
    if custom_deadline is not None and urgency_option == "WITHIN_24H":
        # Preserve backward-compatible callers that pass an explicit spoilage_deadline_at.
        urgency_option = "CUSTOM"

    schedule = compute_deadline_schedule(
        now=now,
        urgency_option=urgency_option,
        custom_collection_deadline_at=custom_deadline,
    )

    if schedule.collection_deadline_at <= harvested_at:
        raise AppError(
            code="invalid_spoilage_deadline",
            message="Collection deadline must be after harvested_at",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    crop = db.scalar(select(CropCatalog).where(CropCatalog.id == payload.crop_id))
    if crop is None:
        raise AppError(
            code="crop_not_found",
            message="Crop catalog entry not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    listing = ProduceListing(
        farmer_id=farmer.id,
        created_by_user_id=current_user.id,
        crop_id=crop.id,
        status=ListingStatus.ACTIVE,
        total_quantity_grams=total_grams,
        available_quantity_grams=total_grams,
        reserved_quantity_grams=0,
        collected_quantity_grams=0,
        floor_price_paise_per_kg=payload.floor_price_paise_per_kg,
        harvested_at=harvested_at,
        spoilage_deadline_at=schedule.collection_deadline_at,
        approx_location_label=payload.approx_location_label,
        approx_latitude=payload.approx_latitude,
        approx_longitude=payload.approx_longitude,
        exact_pickup_address=payload.exact_pickup_address,
        quality_grade=payload.quality_grade,
        photo_urls_json=payload.photo_urls,
        transport_responsibility=payload.transport_responsibility,
        auto_allocate_approved=payload.auto_allocate_approved,
        urgency_option=schedule.urgency_option,
        is_direct_offer_mode=schedule.is_direct_offer_mode,
        bidding_initial_close_at=schedule.initial_bidding_close_at,
        bidding_hard_close_at=schedule.hard_bidding_close_at,
        farmer_approval_deadline_at=schedule.farmer_approval_deadline_at,
        buyer_confirmation_deadline_at=schedule.buyer_confirmation_deadline_at,
        recovery_deadline_at=schedule.recovery_deadline_at,
    )
    db.add(listing)
    db.flush()

    auction = Auction(
        listing_id=listing.id,
        status=AuctionStatus.OPEN,
        min_bid_paise_per_kg=payload.floor_price_paise_per_kg,
        starts_at=schedule.auction_opens_at,
        ends_at=schedule.initial_bidding_close_at,
        hard_close_at=schedule.hard_bidding_close_at,
    )
    db.add(auction)
    db.flush()

    enqueue_job(
        db,
        job_type="AUCTION_CLOSE",
        payload={"auction_id": str(auction.id)},
        run_at=auction.ends_at,
    )

    record_audit_event(
        db,
        actor_user_id=current_user.id,
        acting_as_farmer_id=farmer.id if current_user.role == UserRole.OPERATOR else None,
        action="LISTING_CREATED",
        resource_type="produce_listing",
        resource_id=str(listing.id),
        metadata={
            "urgency_option": schedule.urgency_option,
            "is_direct_offer_mode": schedule.is_direct_offer_mode,
            "consent_recorded": payload.consent_confirmed,
            "auction_id": str(auction.id),
        },
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(listing)
    db.refresh(auction)
    return to_farmer_listing_detail(listing, auction)


def update_produce_listing(
    db: Session,
    *,
    listing_id: uuid.UUID,
    payload: UpdateListingRequest,
    current_user: User,
    ip_address: str | None = None,
) -> FarmerListingDetailResponse:
    listing = db.scalar(select(ProduceListing).where(ProduceListing.id == listing_id))
    if listing is None:
        raise AppError(
            code="listing_not_found",
            message="Produce listing not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    authorize_farmer_access(farmer_id=listing.farmer_id, current_user=current_user, db=db)

    has_committed_inventory = (
        listing.reserved_quantity_grams > 0 or listing.collected_quantity_grams > 0
    )

    if payload.floor_price_paise_per_kg is not None:
        if has_committed_inventory:
            raise AppError(
                code="committed_inventory_locked",
                message="Agreed floor price cannot be modified once inventory is committed",
                status_code=status.HTTP_409_CONFLICT,
            )
        listing.floor_price_paise_per_kg = payload.floor_price_paise_per_kg

    if payload.status is not None and payload.status != listing.status:
        allowed = ALLOWED_LISTING_TRANSITIONS.get(listing.status, set())
        if payload.status not in allowed:
            raise AppError(
                code="invalid_listing_transition",
                message=(
                    f"Transition from {listing.status.value} to {payload.status.value} "
                    "is not allowed"
                ),
                status_code=status.HTTP_409_CONFLICT,
            )
        if payload.status == ListingStatus.CANCELLED and has_committed_inventory:
            raise AppError(
                code="committed_inventory_locked",
                message=(
                    "Cannot cancel entire listing while committed inventory exists; "
                    "cancel uncommitted quantity instead"
                ),
                status_code=status.HTTP_409_CONFLICT,
            )
        listing.status = payload.status

    record_audit_event(
        db,
        actor_user_id=current_user.id,
        acting_as_farmer_id=listing.farmer_id if current_user.role == UserRole.OPERATOR else None,
        action="LISTING_UPDATED",
        resource_type="produce_listing",
        resource_id=str(listing.id),
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(listing)
    auction = db.scalar(select(Auction).where(Auction.listing_id == listing.id))
    return to_farmer_listing_detail(listing, auction)


def cancel_uncommitted_inventory(
    db: Session,
    *,
    listing_id: uuid.UUID,
    current_user: User,
    ip_address: str | None = None,
) -> FarmerListingDetailResponse:
    """Cancel only uncommitted available_quantity_grams while preserving committed quantities."""
    listing = db.scalar(select(ProduceListing).where(ProduceListing.id == listing_id))
    if listing is None:
        raise AppError(
            code="listing_not_found",
            message="Produce listing not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    authorize_farmer_access(farmer_id=listing.farmer_id, current_user=current_user, db=db)

    cancelled_grams = listing.available_quantity_grams
    committed_grams = listing.reserved_quantity_grams + listing.collected_quantity_grams
    listing.available_quantity_grams = 0
    if committed_grams > 0:
        listing.total_quantity_grams = committed_grams
        listing.status = ListingStatus.FULLY_ALLOCATED
    else:
        listing.status = ListingStatus.CANCELLED

    auction = db.scalar(select(Auction).where(Auction.listing_id == listing.id))
    if auction is not None and committed_grams == 0:
        auction.status = AuctionStatus.CANCELLED

    record_audit_event(
        db,
        actor_user_id=current_user.id,
        acting_as_farmer_id=listing.farmer_id if current_user.role == UserRole.OPERATOR else None,
        action="LISTING_UNCOMMITTED_CANCELLED",
        resource_type="produce_listing",
        resource_id=str(listing.id),
        metadata={"cancelled_available_grams": cancelled_grams},
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(listing)
    if auction is not None:
        db.refresh(auction)
    return to_farmer_listing_detail(listing, auction)
