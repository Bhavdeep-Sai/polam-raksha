import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.modules.admin.schemas import (
    AdminOperationalOverview,
    AdminUserSummary,
    AuditEventSummary,
    DisputeCaseSummary,
    OperatorPermissionSummary,
    ResolveDisputeRequest,
    UpdateUserStatusRequest,
    VerifyBuyerRequest,
)
from app.modules.admin.service import (
    get_operational_overview,
    list_admin_users,
    list_audit_events,
    list_disputes,
    list_operator_permissions,
    resolve_dispute,
    revoke_operator_permission,
    update_user_status,
    verify_buyer_profile,
)
from app.modules.auth.dependencies import require_roles
from app.modules.users.models import User, UserRole

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/overview",
    response_model=AdminOperationalOverview,
    summary="Get operational monitoring, worker, and external integration health",
)
def admin_overview(
    _admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AdminOperationalOverview:
    return get_operational_overview(db, settings=settings)


@router.get(
    "/users",
    response_model=list[AdminUserSummary],
    summary="List farmers, buyers, and operators",
)
def admin_list_users(
    _admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    role: Annotated[UserRole | None, Query()] = None,
) -> list[AdminUserSummary]:
    return list_admin_users(db, role=role)


@router.patch(
    "/users/{user_id}/status",
    response_model=AdminUserSummary,
    summary="Activate or deactivate a user account (records audit event)",
)
def admin_update_user_status(
    user_id: uuid.UUID,
    payload: UpdateUserStatusRequest,
    request: Request,
    admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> AdminUserSummary:
    ip = request.client.host if request.client else None
    return update_user_status(
        db,
        admin=admin,
        target_user_id=user_id,
        payload=payload,
        ip_address=ip,
    )


@router.post(
    "/buyers/{buyer_id}/verify",
    response_model=AdminUserSummary,
    summary="Review and update buyer verification status (records audit event)",
)
def admin_verify_buyer(
    buyer_id: uuid.UUID,
    payload: VerifyBuyerRequest,
    request: Request,
    admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> AdminUserSummary:
    ip = request.client.host if request.client else None
    return verify_buyer_profile(
        db,
        admin=admin,
        buyer_user_id=buyer_id,
        payload=payload,
        ip_address=ip,
    )


@router.get(
    "/operator-permissions",
    response_model=list[OperatorPermissionSummary],
    summary="List operator assisted-access relationships",
)
def admin_list_operator_permissions(
    _admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> list[OperatorPermissionSummary]:
    return list_operator_permissions(db)


@router.post(
    "/operator-permissions/{relationship_id}/revoke",
    response_model=OperatorPermissionSummary,
    summary="Revoke an operator assisted-access relationship (records audit event)",
)
def admin_revoke_operator_permission(
    relationship_id: uuid.UUID,
    request: Request,
    admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> OperatorPermissionSummary:
    ip = request.client.host if request.client else None
    return revoke_operator_permission(
        db,
        admin=admin,
        relationship_id=relationship_id,
        ip_address=ip,
    )


@router.get(
    "/disputes",
    response_model=list[DisputeCaseSummary],
    summary="List dispute cases for review",
)
def admin_list_disputes(
    _admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> list[DisputeCaseSummary]:
    return list_disputes(db)


@router.post(
    "/disputes/{dispute_id}/resolve",
    response_model=DisputeCaseSummary,
    summary="Update or resolve a dispute case (records audit event)",
)
def admin_resolve_dispute(
    dispute_id: uuid.UUID,
    payload: ResolveDisputeRequest,
    request: Request,
    admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> DisputeCaseSummary:
    ip = request.client.host if request.client else None
    return resolve_dispute(
        db,
        admin=admin,
        dispute_id=dispute_id,
        payload=payload,
        ip_address=ip,
    )


@router.get(
    "/audit-events",
    response_model=list[AuditEventSummary],
    summary="Explore immutable audit events",
)
def admin_audit_events(
    _admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    action: Annotated[str | None, Query()] = None,
    resource_type: Annotated[str | None, Query()] = None,
) -> list[AuditEventSummary]:
    return list_audit_events(db, action=action, resource_type=resource_type)
