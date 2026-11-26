import uuid
from datetime import datetime

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.modules.admin.schemas import (
    AdminOperationalOverview,
    AdminUserSummary,
    AuditEventSummary,
    DisputeCaseSummary,
    IntegrationHealthItem,
    OperatorPermissionSummary,
    ResolveDisputeRequest,
    UpdateUserStatusRequest,
    VerifyBuyerRequest,
)
from app.modules.auctions.models import Auction, AuctionStatus
from app.modules.listings.models import ListingStatus, ProduceListing
from app.modules.orders.models import DisputeCase, Order, OrderStatus
from app.modules.system.models import AuditEvent, ScheduledJob, TransactionalOutboxEvent
from app.modules.users.models import (
    AssistedAccessRelationship,
    BuyerProfile,
    FarmerProfile,
    User,
    UserRole,
)
from app.shared.time import utc_now


def _record_admin_audit(
    db: Session,
    *,
    admin: User,
    action: str,
    resource_type: str,
    resource_id: str,
    metadata: dict[str, object],
    ip_address: str | None,
) -> None:
    db.add(
        AuditEvent(
            actor_user_id=admin.id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata_json=metadata,
            ip_address=ip_address,
        )
    )


def list_admin_users(
    db: Session, *, role: UserRole | None = None, limit: int = 100
) -> list[AdminUserSummary]:
    stmt = select(User).order_by(User.created_at.desc()).limit(limit)
    if role is not None:
        stmt = stmt.where(User.role == role)
    users = db.scalars(stmt).all()
    if not users:
        return []

    farmer_ids = [u.id for u in users if u.role == UserRole.FARMER]
    buyer_ids = [u.id for u in users if u.role == UserRole.BUYER]
    farmer_profiles = (
        {
            fp.user_id: fp
            for fp in db.scalars(
                select(FarmerProfile).where(FarmerProfile.user_id.in_(farmer_ids))
            ).all()
        }
        if farmer_ids
        else {}
    )
    buyer_profiles = (
        {
            bp.user_id: bp
            for bp in db.scalars(
                select(BuyerProfile).where(BuyerProfile.user_id.in_(buyer_ids))
            ).all()
        }
        if buyer_ids
        else {}
    )

    results: list[AdminUserSummary] = []
    for u in users:
        district: str | None = None
        verification_status: str | None = None
        is_restricted: bool | None = None
        reliability_score: int | None = None
        if u.role == UserRole.FARMER:
            fp = farmer_profiles.get(u.id)
            if fp is not None:
                district = fp.district
        elif u.role == UserRole.BUYER:
            bp = buyer_profiles.get(u.id)
            if bp is not None:
                district = bp.district
                verification_status = bp.verification_status
                is_restricted = bp.is_restricted
                reliability_score = bp.reliability_score

        results.append(
            AdminUserSummary(
                id=u.id,
                full_name=u.full_name,
                email=u.email,
                phone_number=u.phone_number,
                role=u.role.value,
                is_active=u.is_active,
                district=district,
                verification_status=verification_status,
                is_restricted=is_restricted,
                reliability_score=reliability_score,
                created_at=u.created_at,
            )
        )
    return results


def update_user_status(
    db: Session,
    *,
    admin: User,
    target_user_id: uuid.UUID,
    payload: UpdateUserStatusRequest,
    ip_address: str | None,
) -> AdminUserSummary:
    user = db.scalar(select(User).where(User.id == target_user_id))
    if user is None:
        raise AppError(
            code="user_not_found",
            message="User not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if user.id == admin.id and not payload.is_active:
        raise AppError(
            code="cannot_deactivate_self",
            message="Administrators cannot deactivate their own account",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    previous = user.is_active
    user.is_active = payload.is_active
    _record_admin_audit(
        db,
        admin=admin,
        action="ADMIN_USER_STATUS_UPDATED",
        resource_type="user",
        resource_id=str(user.id),
        metadata={
            "previous_is_active": previous,
            "new_is_active": payload.is_active,
            "reason": payload.reason,
        },
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(user)
    return AdminUserSummary(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone_number=user.phone_number,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at,
    )


def verify_buyer_profile(
    db: Session,
    *,
    admin: User,
    buyer_user_id: uuid.UUID,
    payload: VerifyBuyerRequest,
    ip_address: str | None,
) -> AdminUserSummary:
    user = db.scalar(select(User).where(User.id == buyer_user_id, User.role == UserRole.BUYER))
    profile = db.scalar(select(BuyerProfile).where(BuyerProfile.user_id == buyer_user_id))
    if user is None or profile is None:
        raise AppError(
            code="buyer_not_found",
            message="Buyer profile not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    prev_status = profile.verification_status
    profile.verification_status = payload.verification_status
    profile.is_restricted = payload.is_restricted
    _record_admin_audit(
        db,
        admin=admin,
        action="ADMIN_BUYER_VERIFIED",
        resource_type="buyer_profile",
        resource_id=str(profile.id),
        metadata={
            "buyer_user_id": str(buyer_user_id),
            "previous_status": prev_status,
            "new_status": payload.verification_status,
            "is_restricted": payload.is_restricted,
            "notes": payload.notes,
        },
        ip_address=ip_address,
    )
    db.commit()
    return AdminUserSummary(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone_number=user.phone_number,
        role=user.role.value,
        is_active=user.is_active,
        district=profile.district,
        verification_status=profile.verification_status,
        is_restricted=profile.is_restricted,
        reliability_score=profile.reliability_score,
        created_at=user.created_at,
    )


def list_operator_permissions(db: Session) -> list[OperatorPermissionSummary]:
    rels = db.scalars(
        select(AssistedAccessRelationship).order_by(AssistedAccessRelationship.granted_at.desc())
    ).all()
    if not rels:
        return []

    user_ids = {r.operator_id for r in rels} | {r.farmer_id for r in rels}
    users_by_id = {
        u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()
    }

    out: list[OperatorPermissionSummary] = []
    for r in rels:
        op_user = users_by_id.get(r.operator_id)
        f_user = users_by_id.get(r.farmer_id)
        out.append(
            OperatorPermissionSummary(
                id=r.id,
                operator_id=r.operator_id,
                operator_name=op_user.full_name if op_user else "Unknown",
                farmer_id=r.farmer_id,
                farmer_name=f_user.full_name if f_user else "Unknown",
                is_active=r.is_active,
                consent_method=r.consent_method,
                granted_at=r.granted_at,
                revoked_at=r.revoked_at,
            )
        )
    return out


def revoke_operator_permission(
    db: Session,
    *,
    admin: User,
    relationship_id: uuid.UUID,
    ip_address: str | None,
) -> OperatorPermissionSummary:
    rel = db.scalar(
        select(AssistedAccessRelationship).where(AssistedAccessRelationship.id == relationship_id)
    )
    if rel is None:
        raise AppError(
            code="permission_not_found",
            message="Assisted-access relationship not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    rel.is_active = False
    rel.revoked_at = utc_now()
    _record_admin_audit(
        db,
        admin=admin,
        action="ADMIN_OPERATOR_PERMISSION_REVOKED",
        resource_type="assisted_access_relationship",
        resource_id=str(rel.id),
        metadata={"operator_id": str(rel.operator_id), "farmer_id": str(rel.farmer_id)},
        ip_address=ip_address,
    )
    db.commit()
    op_user = db.scalar(select(User).where(User.id == rel.operator_id))
    f_user = db.scalar(select(User).where(User.id == rel.farmer_id))
    return OperatorPermissionSummary(
        id=rel.id,
        operator_id=rel.operator_id,
        operator_name=op_user.full_name if op_user else "Unknown",
        farmer_id=rel.farmer_id,
        farmer_name=f_user.full_name if f_user else "Unknown",
        is_active=rel.is_active,
        consent_method=rel.consent_method,
        granted_at=rel.granted_at,
        revoked_at=rel.revoked_at,
    )


def list_disputes(db: Session) -> list[DisputeCaseSummary]:
    rows = db.scalars(select(DisputeCase).order_by(DisputeCase.created_at.desc())).all()
    return [DisputeCaseSummary.model_validate(r, from_attributes=True) for r in rows]


def resolve_dispute(
    db: Session,
    *,
    admin: User,
    dispute_id: uuid.UUID,
    payload: ResolveDisputeRequest,
    ip_address: str | None,
) -> DisputeCaseSummary:
    dispute = db.scalar(select(DisputeCase).where(DisputeCase.id == dispute_id))
    if dispute is None:
        raise AppError(
            code="dispute_not_found",
            message="Dispute case not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    dispute.status = payload.status
    dispute.resolution_notes = payload.resolution_notes
    dispute.resolved_by_admin_id = admin.id
    if payload.status == "RESOLVED":
        dispute.resolved_at = utc_now()
    _record_admin_audit(
        db,
        admin=admin,
        action="ADMIN_DISPUTE_UPDATED",
        resource_type="dispute_case",
        resource_id=str(dispute.id),
        metadata={"status": payload.status, "order_id": str(dispute.order_id)},
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(dispute)
    return DisputeCaseSummary.model_validate(dispute, from_attributes=True)


def list_audit_events(
    db: Session,
    *,
    action: str | None = None,
    resource_type: str | None = None,
    limit: int = 100,
) -> list[AuditEventSummary]:
    stmt = select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)
    if action:
        stmt = stmt.where(AuditEvent.action == action)
    if resource_type:
        stmt = stmt.where(AuditEvent.resource_type == resource_type)
    rows = db.scalars(stmt).all()
    return [AuditEventSummary.model_validate(r, from_attributes=True) for r in rows]


def get_operational_overview(
    db: Session, *, settings: Settings, now: datetime | None = None
) -> AdminOperationalOverview:
    current_time = now or utc_now()
    active_auctions = db.scalar(
        select(func.count(Auction.id)).where(
            Auction.status.in_([AuctionStatus.OPEN, AuctionStatus.CLOSING])
        )
    ) or 0
    pending_confirmations = db.scalar(
        select(func.count(Order.id)).where(Order.status == OrderStatus.PENDING_CONFIRMATION)
    ) or 0
    expired_listings = db.scalar(
        select(func.count(ProduceListing.id)).where(
            ProduceListing.status == ListingStatus.EXPIRED
        )
    ) or 0
    failed_collections = db.scalar(
        select(func.count(Order.id)).where(
            (Order.status.in_([OrderStatus.EXPIRED, OrderStatus.CANCELLED_BY_BUYER]))
            | (
                (Order.status == OrderStatus.CONFIRMED)
                & (Order.pickup_deadline_at < current_time)
            )
        )
    ) or 0
    recovery_events = db.scalar(
        select(func.count(Order.id)).where(Order.status == OrderStatus.RECOVERED)
    ) or 0
    open_disputes = db.scalar(
        select(func.count(DisputeCase.id)).where(DisputeCase.status != "RESOLVED")
    ) or 0
    pending_jobs = db.scalar(
        select(func.count(ScheduledJob.id)).where(ScheduledJob.status == "PENDING")
    ) or 0
    failed_jobs = db.scalar(
        select(func.count(ScheduledJob.id)).where(ScheduledJob.status == "FAILED")
    ) or 0
    unpublished_outbox = db.scalar(
        select(func.count(TransactionalOutboxEvent.id)).where(
            TransactionalOutboxEvent.published_at.is_(None)
        )
    ) or 0

    integrations = [
        IntegrationHealthItem(
            name="OSRM Routing",
            configured=bool(settings.osrm_base_url),
            mode="EXTERNAL_WITH_FALLBACK" if settings.osrm_base_url else "LOCAL_HAVERSINE_FALLBACK",
            detail=settings.osrm_base_url or "Using cached matrix + approximate Haversine fallback",
        ),
        IntegrationHealthItem(
            name="data.gov.in Market Prices",
            configured=bool(settings.data_gov_in_api_key),
            mode="LIVE_API_AVAILABLE" if settings.data_gov_in_api_key else "CSV_LOCAL_IMPORT_ONLY",
            detail=(
                "API key configured"
                if settings.data_gov_in_api_key
                else "Offline CSV/JSON import mode"
            ),
        ),
        IntegrationHealthItem(
            name="Telephony / IVR Webhook",
            configured=bool(settings.ivr_webhook_secret),
            mode="LOCAL_SIMULATOR_AND_WEBHOOK",
            detail="Provider-independent state machine active",
        ),
    ]

    return AdminOperationalOverview(
        active_auctions_count=int(active_auctions),
        pending_confirmations_count=int(pending_confirmations),
        expired_listings_count=int(expired_listings),
        failed_collections_count=int(failed_collections),
        recovery_events_count=int(recovery_events),
        open_disputes_count=int(open_disputes),
        pending_jobs_count=int(pending_jobs),
        failed_jobs_count=int(failed_jobs),
        unpublished_outbox_count=int(unpublished_outbox),
        integrations=integrations,
    )
