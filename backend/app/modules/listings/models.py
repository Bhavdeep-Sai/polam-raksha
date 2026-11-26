import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import JSONBType, UtcDateTime
from app.shared.time import utc_now


class ListingStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PARTIALLY_ALLOCATED = "PARTIALLY_ALLOCATED"
    FULLY_ALLOCATED = "FULLY_ALLOCATED"
    ALLOCATED = "ALLOCATED"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class CropCatalog(Base):
    __tablename__ = "crop_catalog"
    __table_args__ = (
        CheckConstraint("default_shelf_life_hours > 0", name="shelf_life_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name_en: Mapped[str] = mapped_column(String(120), nullable=False)
    name_te: Mapped[str] = mapped_column(String(120), nullable=False)
    unit_label_en: Mapped[str] = mapped_column(String(30), nullable=False, default="kg")
    unit_label_te: Mapped[str] = mapped_column(String(30), nullable=False, default="కిలో")
    default_shelf_life_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=48)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ProduceListing(Base):
    __tablename__ = "produce_listings"
    __table_args__ = (
        CheckConstraint("total_quantity_grams > 0", name="total_qty_positive"),
        CheckConstraint("available_quantity_grams >= 0", name="available_qty_non_negative"),
        CheckConstraint("reserved_quantity_grams >= 0", name="reserved_qty_non_negative"),
        CheckConstraint("collected_quantity_grams >= 0", name="collected_qty_non_negative"),
        CheckConstraint(
            "available_quantity_grams + reserved_quantity_grams + collected_quantity_grams "
            "<= total_quantity_grams",
            name="inventory_sum_within_total",
        ),
        CheckConstraint("floor_price_paise_per_kg > 0", name="floor_price_positive"),
        CheckConstraint("spoilage_deadline_at > harvested_at", name="deadline_after_harvest"),
        Index("ix_produce_listings_farmer_status", "farmer_id", "status"),
        Index("ix_produce_listings_status_deadline", "status", "spoilage_deadline_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    farmer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    crop_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("crop_catalog.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[ListingStatus] = mapped_column(
        Enum(ListingStatus, name="listing_status", native_enum=True),
        nullable=False,
        default=ListingStatus.ACTIVE,
    )
    total_quantity_grams: Mapped[int] = mapped_column(BigInteger, nullable=False)
    available_quantity_grams: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reserved_quantity_grams: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    collected_quantity_grams: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    floor_price_paise_per_kg: Mapped[int] = mapped_column(BigInteger, nullable=False)
    harvested_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    spoilage_deadline_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    approx_location_label: Mapped[str] = mapped_column(String(180), nullable=False)
    approx_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    approx_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    exact_pickup_address: Mapped[str] = mapped_column(Text, nullable=False)
    exact_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    exact_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_grade: Mapped[str] = mapped_column(String(20), nullable=False, default="GRADE_A")
    photo_urls_json: Mapped[list[str]] = mapped_column(JSONBType, nullable=False, default=list)
    transport_responsibility: Mapped[str] = mapped_column(
        String(30), nullable=False, default="BUYER_PICKUP"
    )
    auto_allocate_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    urgency_option: Mapped[str] = mapped_column(String(20), nullable=False, default="WITHIN_24H")
    is_direct_offer_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    bidding_initial_close_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    bidding_hard_close_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    farmer_approval_deadline_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
    buyer_confirmation_deadline_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
    recovery_deadline_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, nullable=False, default=utc_now, onupdate=utc_now
    )
