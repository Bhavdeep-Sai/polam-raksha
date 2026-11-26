import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import JSONBType, UtcDateTime
from app.shared.time import utc_now


class AllocationRunStatus(enum.StrEnum):
    PENDING = "PENDING"
    SOLVED = "SOLVED"
    INFEASIBLE = "INFEASIBLE"
    FAILED = "FAILED"


class AllocationRun(Base):
    __tablename__ = "allocation_runs"
    __table_args__ = (Index("ix_allocation_runs_auction_id", "auction_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    auction_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("auctions.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[AllocationRunStatus] = mapped_column(
        Enum(AllocationRunStatus, name="allocation_run_status", native_enum=True),
        nullable=False,
        default=AllocationRunStatus.PENDING,
    )
    solver_status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    algorithm_version: Mapped[str] = mapped_column(
        String(40), nullable=False, default="cp-sat-v1.0"
    )
    strategy: Mapped[str] = mapped_column(String(30), nullable=False, default="REVENUE_FIRST")
    input_snapshot_json: Mapped[dict[str, Any]] = mapped_column(
        JSONBType, nullable=False, default=dict
    )
    explanations_json: Mapped[list[str]] = mapped_column(
        JSONBType, nullable=False, default=list
    )
    gross_revenue_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    transportation_cost_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    estimated_net_revenue_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    unallocated_quantity_grams: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    execution_time_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approved_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    objective_value_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)


class Allocation(Base):
    __tablename__ = "allocations"
    __table_args__ = (
        CheckConstraint("allocated_quantity_grams > 0", name="allocated_qty_positive"),
        CheckConstraint("unit_price_paise_per_kg > 0", name="unit_price_positive"),
        CheckConstraint("transport_cost_paise >= 0", name="transport_cost_non_negative"),
        Index("ix_allocations_run_id", "allocation_run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    allocation_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("allocation_runs.id", ondelete="RESTRICT"), nullable=False
    )
    auction_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("auctions.id", ondelete="RESTRICT"), nullable=False
    )
    buyer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    allocated_quantity_grams: Mapped[int] = mapped_column(BigInteger, nullable=False)
    unit_price_paise_per_kg: Mapped[int] = mapped_column(BigInteger, nullable=False)
    transport_cost_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, default=utc_now)

