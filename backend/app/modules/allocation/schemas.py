import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.allocation.models import AllocationRunStatus
from app.modules.allocation.solver import AllocationStrategy


class RunAllocationRequest(BaseModel):
    strategy: AllocationStrategy = AllocationStrategy.REVENUE_FIRST
    min_net_revenue_paise: int = Field(default=0, ge=0)
    time_limit_seconds: float = Field(default=2.0, gt=0.01, le=30.0)


class AllocationItemResponse(BaseModel):
    id: uuid.UUID
    buyer_id: uuid.UUID
    allocated_quantity_grams: int
    unit_price_paise_per_kg: int
    transport_cost_paise: int


class AllocationRunResponse(BaseModel):
    id: uuid.UUID
    auction_id: uuid.UUID
    status: AllocationRunStatus
    solver_status: str
    algorithm_version: str
    strategy: str
    gross_revenue_paise: int
    transportation_cost_paise: int
    estimated_net_revenue_paise: int
    unallocated_quantity_grams: int
    execution_time_ms: int
    is_approved: bool
    approved_at: datetime | None
    explanations: list[str]
    allocations: list[AllocationItemResponse]
    created_at: datetime

