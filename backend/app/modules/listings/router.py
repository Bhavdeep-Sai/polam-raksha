import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_db
from app.modules.auctions.models import Auction
from app.modules.auth.dependencies import authorize_farmer_access, get_current_user
from app.modules.listings.deadline_policy import compute_deadline_schedule
from app.modules.listings.models import CropCatalog, ListingStatus, ProduceListing
from app.modules.listings.schemas import (
    CreateListingRequest,
    CropCatalogItem,
    FarmerListingDetailResponse,
    PublicListingResponse,
    SchedulePreviewRequest,
    SchedulePreviewResponse,
    UpdateListingRequest,
)
from app.modules.listings.service import (
    cancel_uncommitted_inventory,
    create_produce_listing,
    list_active_crops,
    to_farmer_listing_detail,
    to_public_listing,
    update_produce_listing,
)
from app.modules.users.models import User
from app.shared.time import utc_now

crops_router = APIRouter(prefix="/crops", tags=["crops"])
router = APIRouter(prefix="/listings", tags=["listings"])


@crops_router.get(
    "",
    response_model=list[CropCatalogItem],
    summary="List bilingual crop catalog",
)
def get_crop_catalog(
    db: Annotated[Session, Depends(get_db)],
) -> list[CropCatalogItem]:
    return list_active_crops(db)


@router.get(
    "",
    response_model=list[PublicListingResponse],
    summary="List active produce listings with approximate locations only",
)
def list_public_listings(
    db: Annotated[Session, Depends(get_db)],
) -> list[PublicListingResponse]:
    rows = db.scalars(
        select(ProduceListing)
        .where(
            ProduceListing.status.in_(
                [ListingStatus.ACTIVE, ListingStatus.PARTIALLY_ALLOCATED]
            )
        )
        .order_by(ProduceListing.spoilage_deadline_at.asc())
    ).all()
    return [to_public_listing(row) for row in rows]


@router.get(
    "/mine",
    response_model=list[FarmerListingDetailResponse],
    summary="List listings for the authenticated farmer or assigned farmer",
)
def list_my_listings(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    farmer_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[FarmerListingDetailResponse]:
    target_farmer_id = farmer_id or current_user.id
    farmer = authorize_farmer_access(
        farmer_id=target_farmer_id,
        current_user=current_user,
        db=db,
    )
    listings = db.scalars(
        select(ProduceListing)
        .where(ProduceListing.farmer_id == farmer.id)
        .order_by(ProduceListing.created_at.desc())
    ).all()
    if not listings:
        return []
    listing_ids = [item.id for item in listings]
    auctions_by_listing = {
        a.listing_id: a
        for a in db.scalars(select(Auction).where(Auction.listing_id.in_(listing_ids))).all()
    }
    return [
        to_farmer_listing_detail(item, auctions_by_listing.get(item.id))
        for item in listings
    ]


@router.post(
    "/schedule-preview",
    response_model=SchedulePreviewResponse,
    summary="Preview feasible auction, approval, recovery, and collection deadlines",
)
def preview_schedule(
    payload: SchedulePreviewRequest,
    _current_user: Annotated[User, Depends(get_current_user)],
) -> SchedulePreviewResponse:
    schedule = compute_deadline_schedule(
        now=utc_now(),
        urgency_option=payload.urgency_option,
        custom_collection_deadline_at=payload.custom_collection_deadline_at,
    )
    return SchedulePreviewResponse(
        urgency_option=schedule.urgency_option,
        is_direct_offer_mode=schedule.is_direct_offer_mode,
        auction_opens_at=schedule.auction_opens_at,
        initial_bidding_close_at=schedule.initial_bidding_close_at,
        hard_bidding_close_at=schedule.hard_bidding_close_at,
        farmer_approval_deadline_at=schedule.farmer_approval_deadline_at,
        buyer_confirmation_deadline_at=schedule.buyer_confirmation_deadline_at,
        recovery_deadline_at=schedule.recovery_deadline_at,
        collection_deadline_at=schedule.collection_deadline_at,
    )


@router.post(
    "",
    response_model=FarmerListingDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a produce listing and linked auction (farmer or assigned operator only)",
)
def create_listing(
    payload: CreateListingRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> FarmerListingDetailResponse:
    ip = request.client.host if request.client else None
    return create_produce_listing(
        db,
        payload=payload,
        current_user=current_user,
        ip_address=ip,
    )


@router.patch(
    "/{listing_id}",
    response_model=FarmerListingDetailResponse,
    summary="Update a produce listing (owner farmer or assigned operator only)",
)
def update_listing(
    listing_id: uuid.UUID,
    payload: UpdateListingRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> FarmerListingDetailResponse:
    ip = request.client.host if request.client else None
    return update_produce_listing(
        db,
        listing_id=listing_id,
        payload=payload,
        current_user=current_user,
        ip_address=ip,
    )


@router.post(
    "/{listing_id}/cancel-uncommitted",
    response_model=FarmerListingDetailResponse,
    summary="Cancel uncommitted available quantity while preserving committed orders",
)
def cancel_uncommitted(
    listing_id: uuid.UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> FarmerListingDetailResponse:
    ip = request.client.host if request.client else None
    return cancel_uncommitted_inventory(
        db,
        listing_id=listing_id,
        current_user=current_user,
        ip_address=ip,
    )


class ListingReceiptResponse(BaseModel):
    listing_id: uuid.UUID
    farmer_id: uuid.UUID
    farmer_name: str
    crop_name_en: str
    crop_name_te: str
    total_quantity_grams: int
    floor_price_paise_per_kg: int
    collection_deadline_at: datetime
    operator_or_centre_info: str


@router.get(
    "/{listing_id}/receipt",
    response_model=ListingReceiptResponse,
    summary="Printable listing receipt for farmers and assisted operators",
)
def get_listing_receipt(
    listing_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ListingReceiptResponse:
    listing = db.scalar(select(ProduceListing).where(ProduceListing.id == listing_id))
    if listing is None:
        raise AppError(
            code="listing_not_found",
            message="Produce listing not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    farmer = authorize_farmer_access(
        farmer_id=listing.farmer_id, current_user=current_user, db=db
    )
    crop = db.scalar(select(CropCatalog).where(CropCatalog.id == listing.crop_id))
    creator = db.scalar(select(User).where(User.id == listing.created_by_user_id))
    centre_info = (
        f"Assisted by {creator.full_name} ({creator.phone_number or 'Operator Centre'})"
        if creator and creator.id != farmer.id
        else "Self-registered via PolamRaksha"
    )
    return ListingReceiptResponse(
        listing_id=listing.id,
        farmer_id=farmer.id,
        farmer_name=farmer.full_name,
        crop_name_en=crop.name_en if crop else "Crop",
        crop_name_te=crop.name_te if crop else "పంట",
        total_quantity_grams=listing.total_quantity_grams,
        floor_price_paise_per_kg=listing.floor_price_paise_per_kg,
        collection_deadline_at=listing.spoilage_deadline_at,
        operator_or_centre_info=centre_info,
    )
