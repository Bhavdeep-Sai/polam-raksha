import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UtcDateTime
from app.shared.time import utc_now


class AuctionStatus(enum.StrEnum):
    SCHEDULED = "SCHEDULED"
    OPEN = "OPEN"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class Auction(Base):
    __tablename__ = "auctions"
    __table_args__ = (
        CheckConstraint("min_bid_paise_per_kg > 0", name="min_bid_positive"),
        CheckConstraint("ends_at > starts_at", name="ends_after_starts"),
        CheckConstraint("version > 0", name="auction_version_positive"),
        CheckConstraint(
            "soft_close_extended_seconds >= 0 "
            "AND soft_close_extended_seconds <= soft_close_max_extension_seconds",
            name="soft_close_extension_bounds",
        ),
        CheckConstraint("min_increment_paise_per_kg > 0", name="min_increment_positive"),
        Index("ix_auctions_status_ends_at", "status", "ends_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("produce_listings.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    status: Mapped[AuctionStatus] = mapped_column(
        Enum(AuctionStatus, name="auction_status", native_enum=True),
        nullable=False,
        default=AuctionStatus.SCHEDULED,
    )
    min_bid_paise_per_kg: Mapped[int] = mapped_column(BigInteger, nullable=False)
    min_increment_paise_per_kg: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=50
    )
    starts_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    ends_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    hard_close_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    soft_close_trigger_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    soft_close_extension_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    soft_close_max_extension_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=600
    )
    soft_close_extended_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    closed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, default=utc_now)


class BidRevision(Base):
    __tablename__ = "bid_revisions"
    __table_args__ = (
        UniqueConstraint("auction_id", "buyer_id", "revision_number", name="uq_bid_revision"),
        UniqueConstraint("auction_id", "buyer_id", "idempotency_key", name="uq_bid_idempotency"),
        CheckConstraint("revision_number > 0", name="revision_positive"),
        CheckConstraint("bid_price_paise_per_kg > 0", name="bid_price_positive"),
        CheckConstraint("requested_quantity_grams > 0", name="requested_qty_positive"),
        CheckConstraint("min_acceptable_grams > 0", name="min_acceptable_qty_positive"),
        CheckConstraint(
            "min_acceptable_grams <= requested_quantity_grams",
            name="min_qty_lte_requested",
        ),
        CheckConstraint(
            "estimated_transport_cost_paise >= 0",
            name="bid_transport_cost_non_negative",
        ),
        Index("ix_bid_revisions_auction_active", "auction_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    auction_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("auctions.id", ondelete="RESTRICT"), nullable=False
    )
    buyer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    bid_price_paise_per_kg: Mapped[int] = mapped_column(BigInteger, nullable=False)
    requested_quantity_grams: Mapped[int] = mapped_column(BigInteger, nullable=False)
    min_acceptable_grams: Mapped[int] = mapped_column(BigInteger, nullable=False)
    estimated_collection_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    transport_responsibility: Mapped[str] = mapped_column(
        String(30), nullable=False, default="BUYER_PICKUP"
    )
    estimated_transport_cost_paise: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    standby_until: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, default=utc_now)

