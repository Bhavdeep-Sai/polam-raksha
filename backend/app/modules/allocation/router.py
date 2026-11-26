import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.allocation.schemas import AllocationRunResponse, RunAllocationRequest
from app.modules.allocation.service import (
    approve_allocation_run,
    list_all_allocation_runs,
    list_runs_for_auction,
    run_allocation_for_auction,
)
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.users.models import User, UserRole

router = APIRouter(prefix="/allocations", tags=["allocations"])


@router.post(
    "/auctions/{auction_id}/run",
    response_model=AllocationRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run OR-Tools CP-SAT allocation for an auction",
)
def trigger_allocation_run(
    auction_id: uuid.UUID,
    payload: RunAllocationRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AllocationRunResponse:
    ip = request.client.host if request.client else None
    return run_allocation_for_auction(
        db,
        auction_id=auction_id,
        payload=payload,
        current_user=current_user,
        ip_address=ip,
    )


@router.post(
    "/{run_id}/approve",
    response_model=AllocationRunResponse,
    summary="Farmer or assigned operator approves and commits an allocation run",
)
def approve_allocation(
    run_id: uuid.UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AllocationRunResponse:
    ip = request.client.host if request.client else None
    return approve_allocation_run(
        db,
        run_id=run_id,
        current_user=current_user,
        ip_address=ip,
    )


@router.get(
    "/auctions/{auction_id}",
    response_model=list[AllocationRunResponse],
    summary="List allocation runs and solver explanations for an auction",
)
def get_auction_allocations(
    auction_id: uuid.UUID,
    _current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[AllocationRunResponse]:
    return list_runs_for_auction(db, auction_id=auction_id)


@router.get(
    "/runs",
    response_model=list[AllocationRunResponse],
    summary="List recent allocation runs across the platform (admin only)",
)
def get_admin_allocation_runs(
    _admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> list[AllocationRunResponse]:
    return list_all_allocation_runs(db)

