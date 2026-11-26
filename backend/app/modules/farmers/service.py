import uuid
from datetime import datetime
from typing import Literal

from fastapi import status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.auth.service import record_audit_event
from app.modules.system.models import AuditEvent
from app.modules.users.models import (
    AssistedAccessRelationship,
    FarmerProfile,
    User,
    UserRole,
)

ConsentMethod = Literal["IN_PERSON_VERBAL", "KEYPAD_PIN", "SIGNED_FORM"]


class AssistedFarmerOnboardRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    preferred_language: Literal["te", "en"] = "te"
    phone_number: str | None = Field(default=None, min_length=10, max_length=20)
    village: str = Field(min_length=2, max_length=120)
    mandal: str = Field(default="Unspecified", min_length=2, max_length=120)
    district: str = Field(min_length=2, max_length=120)
    approx_location_label: str | None = Field(default=None, max_length=180)
    exact_pickup_address: str | None = Field(default=None, max_length=500)
    consent_method: ConsentMethod = "IN_PERSON_VERBAL"
    consent_confirmed: bool


class AssistedFarmerSummary(BaseModel):
    farmer_id: uuid.UUID
    full_name: str
    preferred_language: str
    phone_number: str | None
    village: str
    district: str
    consent_method: str
    granted_at: datetime


class AssistedActionAuditItem(BaseModel):
    id: uuid.UUID
    action: str
    acting_as_farmer_id: uuid.UUID | None
    resource_type: str
    resource_id: str | None
    created_at: datetime


class OperatorAssistedOverviewResponse(BaseModel):
    farmers: list[AssistedFarmerSummary]
    audit_history: list[AssistedActionAuditItem]


def onboard_farmer_assisted(
    db: Session,
    *,
    operator: User,
    payload: AssistedFarmerOnboardRequest,
    ip_address: str | None = None,
) -> AssistedFarmerSummary:
    """Register a farmer without requiring Aadhaar, bank details, or smartphone ownership."""
    if not payload.consent_confirmed:
        raise AppError(
            code="farmer_consent_required",
            message="Explicit farmer consent is required for assisted registration",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    if payload.phone_number:
        existing = db.scalar(select(User).where(User.phone_number == payload.phone_number))
        if existing is not None:
            raise AppError(
                code="phone_already_registered",
                message="A user with this phone number already exists",
                status_code=status.HTTP_409_CONFLICT,
            )

    farmer = User(
        full_name=payload.full_name,
        preferred_language=payload.preferred_language,
        phone_number=payload.phone_number,
        role=UserRole.FARMER,
        is_active=True,
    )
    db.add(farmer)
    db.flush()

    profile = FarmerProfile(
        user_id=farmer.id,
        village=payload.village,
        mandal=payload.mandal,
        district=payload.district,
        exact_pickup_address=payload.exact_pickup_address
        or f"{payload.village}, {payload.district}",
    )
    db.add(profile)

    relationship = AssistedAccessRelationship(
        operator_id=operator.id,
        farmer_id=farmer.id,
        is_active=True,
        consent_method=payload.consent_method,
        notes=f"Assisted onboarding via {payload.consent_method}",
    )
    db.add(relationship)
    db.flush()

    record_audit_event(
        db,
        actor_user_id=operator.id,
        acting_as_farmer_id=farmer.id,
        action="OPERATOR_ASSISTED_FARMER_ONBOARDING",
        resource_type="assisted_access_relationship",
        resource_id=str(relationship.id),
        metadata={
            "consent_method": payload.consent_method,
            "consent_confirmed": True,
        },
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(farmer)
    db.refresh(relationship)

    return AssistedFarmerSummary(
        farmer_id=farmer.id,
        full_name=farmer.full_name,
        preferred_language=farmer.preferred_language,
        phone_number=farmer.phone_number,
        village=profile.village,
        district=profile.district,
        consent_method=relationship.consent_method,
        granted_at=relationship.granted_at,
    )


def get_operator_assisted_overview(
    db: Session,
    *,
    operator: User,
) -> OperatorAssistedOverviewResponse:
    rows = db.execute(
        select(AssistedAccessRelationship, User, FarmerProfile)
        .join(User, User.id == AssistedAccessRelationship.farmer_id)
        .join(FarmerProfile, FarmerProfile.user_id == User.id)
        .where(
            AssistedAccessRelationship.operator_id == operator.id,
            AssistedAccessRelationship.is_active.is_(True),
        )
        .order_by(AssistedAccessRelationship.granted_at.desc())
    ).all()

    farmers = [
        AssistedFarmerSummary(
            farmer_id=user.id,
            full_name=user.full_name,
            preferred_language=user.preferred_language,
            phone_number=user.phone_number,
            village=profile.village,
            district=profile.district,
            consent_method=rel.consent_method,
            granted_at=rel.granted_at,
        )
        for rel, user, profile in rows
    ]

    audits = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.actor_user_id == operator.id)
        .order_by(AuditEvent.created_at.desc())
        .limit(30)
    ).all()

    audit_history = [
        AssistedActionAuditItem(
            id=event.id,
            action=event.action,
            acting_as_farmer_id=event.acting_as_farmer_id,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            created_at=event.created_at,
        )
        for event in audits
    ]

    return OperatorAssistedOverviewResponse(
        farmers=farmers,
        audit_history=audit_history,
    )

