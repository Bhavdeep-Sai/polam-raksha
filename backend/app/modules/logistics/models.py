import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UtcDateTime
from app.shared.time import utc_now


class TransportQuote(Base):
    __tablename__ = "transport_quotes"
    __table_args__ = (
        CheckConstraint("distance_meters >= 0", name="distance_non_negative"),
        CheckConstraint("estimated_cost_paise >= 0", name="estimated_cost_non_negative"),
        CheckConstraint("farmer_paid_cost_paise >= 0", name="farmer_paid_cost_non_negative"),
        Index("ix_transport_quotes_listing_buyer", "listing_id", "buyer_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("produce_listings.id", ondelete="CASCADE"), nullable=False
    )
    buyer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    distance_meters: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_kind: Mapped[str] = mapped_column(
        String(30), nullable=False, default="APPROX_STRAIGHT_LINE"
    )
    estimated_travel_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fixed_pickup_cost_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    variable_cost_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    estimated_cost_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    transport_responsibility: Mapped[str] = mapped_column(
        String(30), nullable=False, default="BUYER_PICKUP"
    )
    farmer_paid_cost_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    provider_name: Mapped[str] = mapped_column(
        String(80), nullable=False, default="local_haversine"
    )
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, default=utc_now)


class RoadDistanceCache(Base):
    __tablename__ = "road_distance_cache"
    __table_args__ = (
        CheckConstraint("distance_meters >= 0", name="cache_distance_non_negative"),
        CheckConstraint("duration_seconds >= 0", name="cache_duration_non_negative"),
        Index("ix_road_distance_cache_pair", "origin_key", "dest_key", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    origin_key: Mapped[str] = mapped_column(String(64), nullable=False)
    dest_key: Mapped[str] = mapped_column(String(64), nullable=False)
    distance_meters: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_name: Mapped[str] = mapped_column(String(60), nullable=False, default="osrm")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, default=utc_now)
