import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class AdminUserSummary(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str | None = None
    phone_number: str | None = None
    role: str
    is_active: bool
    district: str | None = None
    verification_status: str | None = None
    is_restricted: bool | None = None
    reliability_score: int | None = None
    created_at: datetime


class UpdateUserStatusRequest(BaseModel):
    is_active: bool
    reason: str = Field(min_length=3, max_length=300)


class VerifyBuyerRequest(BaseModel):
    verification_status: Literal["VERIFIED", "REJECTED", "PENDING"]
    is_restricted: bool = False
    notes: str | None = Field(default=None, max_length=300)


class OperatorPermissionSummary(BaseModel):
    id: uuid.UUID
    operator_id: uuid.UUID
    operator_name: str
    farmer_id: uuid.UUID
    farmer_name: str
    is_active: bool
    consent_method: str
    granted_at: datetime
    revoked_at: datetime | None = None


class DisputeCaseSummary(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    raised_by_user_id: uuid.UUID
    reason: str
    status: str
    resolution_notes: str | None = None
    resolved_by_admin_id: uuid.UUID | None = None
    created_at: datetime
    resolved_at: datetime | None = None


class ResolveDisputeRequest(BaseModel):
    status: Literal["UNDER_REVIEW", "RESOLVED"]
    resolution_notes: str = Field(min_length=3, max_length=500)


class AuditEventSummary(BaseModel):
    id: uuid.UUID
    actor_user_id: uuid.UUID | None = None
    acting_as_farmer_id: uuid.UUID | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    metadata_json: dict[str, Any]
    ip_address: str | None = None
    created_at: datetime


class IntegrationHealthItem(BaseModel):
    name: str
    configured: bool
    mode: str
    detail: str


class AdminOperationalOverview(BaseModel):
    active_auctions_count: int
    pending_confirmations_count: int
    expired_listings_count: int
    failed_collections_count: int
    recovery_events_count: int
    open_disputes_count: int
    pending_jobs_count: int
    failed_jobs_count: int
    unpublished_outbox_count: int
    integrations: list[IntegrationHealthItem]

