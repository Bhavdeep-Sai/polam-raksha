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
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UtcDateTime
from app.shared.time import utc_now


class OrderStatus(enum.StrEnum):
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    IN_TRANSIT = "IN_TRANSIT"
    COLLECTED = "COLLECTED"
    CANCELLED_BY_BUYER = "CANCELLED_BY_BUYER"
    RECOVERED = "RECOVERED"
    EXPIRED = "EXPIRED"


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("quantity_grams > 0", name="order_qty_positive"),
        CheckConstraint("total_amount_paise >= 0", name="order_amount_non_negative"),
        CheckConstraint("transport_cost_paise >= 0", name="order_transport_non_negative"),
        Index("ix_orders_buyer_status", "buyer_id", "status"),
        Index("ix_orders_farmer_status", "farmer_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    allocation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("allocations.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("produce_listings.id", ondelete="RESTRICT"), nullable=False
    )
    farmer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    buyer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status", native_enum=True),
        nullable=False,
        default=OrderStatus.PENDING_CONFIRMATION,
    )
    quantity_grams: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    transport_cost_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    pickup_deadline_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, nullable=False, default=utc_now, onupdate=utc_now
    )


class CollectionRecord(Base):
    __tablename__ = "collection_records"
    __table_args__ = (
        CheckConstraint("collected_quantity_grams > 0", name="collected_qty_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    collected_quantity_grams: Mapped[int] = mapped_column(BigInteger, nullable=False)
    collected_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, default=utc_now)
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class DisputeCase(Base):
    __tablename__ = "dispute_cases"
    __table_args__ = (Index("ix_dispute_cases_status", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
    )
    raised_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, default=utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)

