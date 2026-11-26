import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.modules.auctions.models import AuctionStatus

TransportResponsibility = Literal["BUYER_PICKUP", "FARMER_DELIVERY", "SHARED"]


class PlaceBidRequest(BaseModel):
    bid_price_paise_per_kg: int = Field(gt=0)
    requested_quantity_grams: int = Field(gt=0)
    min_acceptable_grams: int = Field(gt=0)
    estimated_collection_at: datetime
    transport_responsibility: TransportResponsibility = "BUYER_PICKUP"
    estimated_transport_cost_paise: int = Field(default=0, ge=0)
    standby_until: datetime
    idempotency_key: str = Field(min_length=4, max_length=128)

    @model_validator(mode="after")
    def validate_quantities(self) -> "PlaceBidRequest":
        if self.min_acceptable_grams > self.requested_quantity_grams:
            raise ValueError("min_acceptable_grams cannot exceed requested_quantity_grams")
        return self


class BidRevisionPublicResponse(BaseModel):
    id: uuid.UUID
    auction_id: uuid.UUID
    buyer_alias: str
    is_own_bid: bool
    revision_number: int
    bid_price_paise_per_kg: int
    requested_quantity_grams: int
    min_acceptable_grams: int
    estimated_collection_at: datetime
    transport_responsibility: str
    estimated_transport_cost_paise: int
    standby_until: datetime
    is_active: bool
    created_at: datetime


class AuctionDetailResponse(BaseModel):
    id: uuid.UUID
    listing_id: uuid.UUID
    status: AuctionStatus
    min_bid_paise_per_kg: int
    min_increment_paise_per_kg: int
    starts_at: datetime
    ends_at: datetime
    hard_close_at: datetime
    soft_close_trigger_seconds: int
    soft_close_extension_seconds: int
    soft_close_max_extension_seconds: int
    soft_close_extended_seconds: int
    version: int
    server_time_utc: datetime
    available_quantity_grams: int
    spoilage_deadline_at: datetime
    approx_location_label: str
    is_direct_offer_mode: bool
    highest_unit_price_paise_per_kg: int | None
    soft_closed_triggered: bool = False
    active_offers: list[BidRevisionPublicResponse]
    my_bid_revisions: list[BidRevisionPublicResponse]


class AuctionEventEnvelope(BaseModel):
    event_id: uuid.UUID
    event_type: str
    auction_id: uuid.UUID
    server_timestamp: datetime
    entity_version: int
    payload: dict[str, Any]

