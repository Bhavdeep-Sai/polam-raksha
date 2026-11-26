import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_db
from app.modules.auth.dependencies import (
    authorize_farmer_access,
    get_current_user,
    require_roles,
)
from app.modules.auth.service import record_audit_event
from app.modules.farmers.service import (
    AssistedFarmerOnboardRequest,
    AssistedFarmerSummary,
    OperatorAssistedOverviewResponse,
    get_operator_assisted_overview,
    onboard_farmer_assisted,
)
from app.modules.users.models import FarmerProfile, User, UserRole

router = APIRouter(prefix="/farmers", tags=["farmers"])


class FarmerPrivateProfileResponse(BaseModel):
    farmer_id: uuid.UUID
    full_name: str
    phone_number: str | None
    village: str
    mandal: str
    district: str
    state: str
    exact_pickup_address: str


@router.post(
    "/assisted",
    response_model=AssistedFarmerSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Register a farmer via an authorized operator with recorded consent",
)
def create_assisted_farmer(
    payload: AssistedFarmerOnboardRequest,
    request: Request,
    operator: Annotated[User, Depends(require_roles(UserRole.OPERATOR))],
    db: Annotated[Session, Depends(get_db)],
) -> AssistedFarmerSummary:
    ip = request.client.host if request.client else None
    return onboard_farmer_assisted(
        db,
        operator=operator,
        payload=payload,
        ip_address=ip,
    )


@router.get(
    "/assisted",
    response_model=OperatorAssistedOverviewResponse,
    summary="List farmers assigned to the current operator and assisted audit history",
)
def list_assisted_farmers(
    operator: Annotated[User, Depends(require_roles(UserRole.OPERATOR))],
    db: Annotated[Session, Depends(get_db)],
) -> OperatorAssistedOverviewResponse:
    return get_operator_assisted_overview(db, operator=operator)


@router.get(
    "/{farmer_id}/profile",
    response_model=FarmerPrivateProfileResponse,
    summary="Get private farmer profile (farmer owner or assigned operator only)",
)
def get_farmer_private_profile(
    farmer_id: uuid.UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> FarmerPrivateProfileResponse:
    farmer = authorize_farmer_access(farmer_id=farmer_id, current_user=current_user, db=db)
    profile = db.scalar(select(FarmerProfile).where(FarmerProfile.user_id == farmer.id))
    if profile is None:
        raise AppError(
            code="farmer_profile_not_found",
            message="Farmer profile not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if current_user.role == UserRole.OPERATOR:
        record_audit_event(
            db,
            actor_user_id=current_user.id,
            acting_as_farmer_id=farmer.id,
            action="OPERATOR_VIEWED_FARMER_PROFILE",
            resource_type="farmer_profile",
            resource_id=str(profile.id),
            ip_address=request.client.host if request.client else None,
        )
        db.commit()

    return FarmerPrivateProfileResponse(
        farmer_id=farmer.id,
        full_name=farmer.full_name,
        phone_number=farmer.phone_number,
        village=profile.village,
        mandal=profile.mandal,
        district=profile.district,
        state=profile.state,
        exact_pickup_address=profile.exact_pickup_address,
    )
