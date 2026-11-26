import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.modules.auctions.models import AuctionStatus
from app.modules.listings.deadline_policy import UrgencyOption
from app.modules.listings.models import ListingStatus

QuantityUnit = Literal["GRAM", "KG", "QUINTAL"]
QualityGrade = Literal["GRADE_A", "GRADE_B", "STANDARD"]
TransportResponsibility = Literal["BUYER_PICKUP", "FARMER_DELIVERY", "SHARED"]


class CropCatalogItem(BaseModel):
    id: uuid.UUID
    code: str
    name_en: str
    name_te: str
    unit_label_en: str
    unit_label_te: str
    default_shelf_life_hours: int


class PublicListingResponse(BaseModel):
    """Public listing view exposing only approximate location (never farmer PII)."""

    id: uuid.UUID
    crop_id: uuid.UUID
    status: ListingStatus
    available_quantity_grams: int
    floor_price_paise_per_kg: int
    harvested_at: datetime
    spoilage_deadline_at: datetime
    approx_location_label: str
    approx_latitude: float | None
    approx_longitude: float | None
    quality_grade: str
    transport_responsibility: str
    urgency_option: str
    is_direct_offer_mode: bool
    is_simulated: bool


class FarmerListingDetailResponse(PublicListingResponse):
    """Owner/assigned-operator view including inventory breakdown and auction schedule."""

    farmer_id: uuid.UUID
    created_by_user_id: uuid.UUID
    total_quantity_grams: int
    reserved_quantity_grams: int
    collected_quantity_grams: int
    auto_allocate_approved: bool
    bidding_initial_close_at: datetime | None
    bidding_hard_close_at: datetime | None
    farmer_approval_deadline_at: datetime | None
    buyer_confirmation_deadline_at: datetime | None
    recovery_deadline_at: datetime | None
    auction_id: uuid.UUID | None
    auction_status: AuctionStatus | None


class CreateListingRequest(BaseModel):
    farmer_id: uuid.UUID | None = None
    crop_id: uuid.UUID
    quantity_value: float | None = Field(default=None, gt=0)
    quantity_unit: QuantityUnit = "KG"
    total_quantity_grams: int | None = Field(default=None, gt=0)
    floor_price_paise_per_kg: int = Field(gt=0)
    harvested_at: datetime
    spoilage_deadline_at: datetime | None = None
    urgency_option: UrgencyOption = "WITHIN_24H"
    quality_grade: QualityGrade = "GRADE_A"
    photo_urls: list[str] = Field(default_factory=list, max_length=5)
    transport_responsibility: TransportResponsibility = "BUYER_PICKUP"
    auto_allocate_approved: bool = False
    approx_location_label: str = Field(min_length=2, max_length=180)
    approx_latitude: float | None = None
    approx_longitude: float | None = None
    exact_pickup_address: str = Field(min_length=3, max_length=500)
    consent_confirmed: bool = True

    @field_validator("photo_urls")
    @classmethod
    def validate_photo_urls(cls, value: list[str]) -> list[str]:
        for url in value:
            if len(url) > 500 or not (url.startswith("https://") or url.startswith("http://")):
                raise ValueError(
                    "Photo URLs must start with http:// or https:// and be <= 500 chars"
                )
        return value


class UpdateListingRequest(BaseModel):
    floor_price_paise_per_kg: int | None = Field(default=None, gt=0)
    status: ListingStatus | None = None


class SchedulePreviewRequest(BaseModel):
    urgency_option: UrgencyOption
    custom_collection_deadline_at: datetime | None = None


class SchedulePreviewResponse(BaseModel):
    urgency_option: UrgencyOption
    is_direct_offer_mode: bool
    auction_opens_at: datetime
    initial_bidding_close_at: datetime
    hard_bidding_close_at: datetime
    farmer_approval_deadline_at: datetime
    buyer_confirmation_deadline_at: datetime
    recovery_deadline_at: datetime
    collection_deadline_at: datetime

