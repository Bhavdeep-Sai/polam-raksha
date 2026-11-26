import uuid
from datetime import timedelta
from typing import Any

from fastapi import status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    generate_opaque_token,
    hash_secret,
    hash_token,
    verify_secret,
)
from app.modules.auth.schemas import RegisterRequest, TokenResponse, UserSummary
from app.modules.system.models import AuditEvent
from app.modules.users.models import BuyerProfile, FarmerProfile, RefreshToken, User, UserRole
from app.shared.time import utc_now


def record_audit_event(
    db: Session,
    *,
    actor_user_id: uuid.UUID | None,
    acting_as_farmer_id: uuid.UUID | None = None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditEvent:
    """Append an immutable audit event inside the current database transaction."""
    event = AuditEvent(
        actor_user_id=actor_user_id,
        acting_as_farmer_id=acting_as_farmer_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata_json=metadata or {},
        ip_address=ip_address,
    )
    db.add(event)
    return event


def _to_user_summary(user: User) -> UserSummary:
    return UserSummary(
        id=user.id,
        full_name=user.full_name,
        role=user.role,
        preferred_language=user.preferred_language,
        is_active=user.is_active,
    )


def _issue_tokens(
    db: Session,
    *,
    user: User,
    settings: Settings,
    family_id: uuid.UUID | None = None,
) -> tuple[TokenResponse, str]:
    access_token, expires_in = create_access_token(
        user_id=user.id,
        role=user.role,
        settings=settings,
    )
    raw_refresh = generate_opaque_token()
    refresh_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_refresh),
        family_id=family_id or uuid.uuid4(),
        expires_at=utc_now() + timedelta(days=settings.jwt_refresh_token_expire_days),
    )
    db.add(refresh_record)
    db.flush()

    return (
        TokenResponse(
            access_token=access_token,
            expires_in_seconds=expires_in,
            user=_to_user_summary(user),
        ),
        raw_refresh,
    )


def register_user(
    db: Session,
    *,
    payload: RegisterRequest,
    ip_address: str | None = None,
) -> UserSummary:
    """Register a new FARMER or BUYER with Argon2-hashed credentials."""
    if payload.email:
        existing_email = db.scalar(select(User).where(User.email == payload.email))
        if existing_email is not None:
            raise AppError(
                code="email_already_registered",
                message="An account with this email already exists",
                status_code=status.HTTP_409_CONFLICT,
            )

    if payload.phone_number:
        existing_phone = db.scalar(select(User).where(User.phone_number == payload.phone_number))
        if existing_phone is not None:
            raise AppError(
                code="phone_already_registered",
                message="An account with this phone number already exists",
                status_code=status.HTTP_409_CONFLICT,
            )

    user = User(
        email=payload.email,
        phone_number=payload.phone_number,
        full_name=payload.full_name,
        preferred_language=payload.preferred_language,
        role=payload.role,
        password_hash=hash_secret(payload.password) if payload.password else None,
        pin_hash=hash_secret(payload.pin) if payload.pin else None,
    )
    db.add(user)
    db.flush()

    if payload.role == UserRole.FARMER:
        db.add(
            FarmerProfile(
                user_id=user.id,
                village=payload.village or "Unspecified",
                mandal=payload.mandal or "Unspecified",
                district=payload.district or "Unspecified",
                exact_pickup_address=payload.exact_pickup_address or "Pending verification",
            )
        )
    elif payload.role == UserRole.BUYER:
        db.add(
            BuyerProfile(
                user_id=user.id,
                business_name=payload.business_name or payload.full_name,
                buyer_type=payload.buyer_type or "wholesaler",
                district=payload.district or "Unspecified",
            )
        )

    record_audit_event(
        db,
        actor_user_id=user.id,
        action="USER_REGISTERED",
        resource_type="user",
        resource_id=str(user.id),
        metadata={"role": user.role.value},
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(user)
    return _to_user_summary(user)


def authenticate_password(
    db: Session,
    *,
    identifier: str,
    password: str,
    settings: Settings,
    ip_address: str | None = None,
) -> tuple[TokenResponse, str]:
    """Authenticate a user via email/phone and Argon2 password."""
    user = db.scalar(
        select(User).where(or_(User.email == identifier, User.phone_number == identifier))
    )
    if (
        user is None
        or not user.is_active
        or not user.password_hash
        or not verify_secret(password, user.password_hash)
    ):
        raise AppError(
            code="invalid_credentials",
            message="Invalid login credentials",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    token_response, raw_refresh = _issue_tokens(db, user=user, settings=settings)
    record_audit_event(
        db,
        actor_user_id=user.id,
        action="AUTH_LOGIN_PASSWORD",
        resource_type="user",
        resource_id=str(user.id),
        ip_address=ip_address,
    )
    db.commit()
    return token_response, raw_refresh


def authenticate_pin(
    db: Session,
    *,
    phone_number: str,
    pin: str,
    settings: Settings,
    ip_address: str | None = None,
) -> tuple[TokenResponse, str]:
    """Authenticate a keypad-phone user via phone_number + Argon2 PIN with lockout."""
    user = db.scalar(select(User).where(User.phone_number == phone_number))
    now = utc_now()

    if user is None or not user.is_active or not user.pin_hash:
        raise AppError(
            code="invalid_pin_credentials",
            message="Invalid phone number or PIN",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if user.pin_locked_until is not None:
        locked_until = user.pin_locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=now.tzinfo)
        if locked_until > now:
            raise AppError(
                code="pin_locked",
                message="Too many failed PIN attempts. Please try again later.",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )

    if not verify_secret(pin, user.pin_hash):
        user.failed_pin_attempts += 1
        if user.failed_pin_attempts >= settings.pin_max_failed_attempts:
            user.pin_locked_until = now + timedelta(minutes=settings.pin_lockout_minutes)
        record_audit_event(
            db,
            actor_user_id=user.id,
            action="AUTH_PIN_FAILED",
            resource_type="user",
            resource_id=str(user.id),
            metadata={"failed_attempts": user.failed_pin_attempts},
            ip_address=ip_address,
        )
        db.commit()
        raise AppError(
            code="invalid_pin_credentials",
            message="Invalid phone number or PIN",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    user.failed_pin_attempts = 0
    user.pin_locked_until = None
    token_response, raw_refresh = _issue_tokens(db, user=user, settings=settings)
    record_audit_event(
        db,
        actor_user_id=user.id,
        action="AUTH_LOGIN_PIN",
        resource_type="user",
        resource_id=str(user.id),
        ip_address=ip_address,
    )
    db.commit()
    return token_response, raw_refresh


def rotate_refresh_token(
    db: Session,
    *,
    raw_refresh_token: str,
    settings: Settings,
    ip_address: str | None = None,
) -> tuple[TokenResponse, str]:
    """Validate and rotate a refresh token; revoke entire family on token reuse."""
    token_digest = hash_token(raw_refresh_token)
    existing = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_digest))
    now = utc_now()

    if existing is None:
        raise AppError(
            code="invalid_refresh_token",
            message="Refresh token is invalid",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if existing.revoked_at is not None:
        # Reuse detected: revoke all active tokens in this family.
        family_tokens = db.scalars(
            select(RefreshToken).where(
                RefreshToken.family_id == existing.family_id,
                RefreshToken.revoked_at.is_(None),
            )
        ).all()
        for tok in family_tokens:
            tok.revoked_at = now
        record_audit_event(
            db,
            actor_user_id=existing.user_id,
            action="REFRESH_TOKEN_REUSE_DETECTED",
            resource_type="refresh_token",
            resource_id=str(existing.id),
            ip_address=ip_address,
        )
        db.commit()
        raise AppError(
            code="refresh_token_reused",
            message="Refresh token has already been used or revoked",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    expires_at = existing.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=now.tzinfo)
    if expires_at <= now:
        existing.revoked_at = now
        db.commit()
        raise AppError(
            code="refresh_token_expired",
            message="Refresh token has expired",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    user = db.scalar(select(User).where(User.id == existing.user_id))
    if user is None or not user.is_active:
        raise AppError(
            code="inactive_or_missing_user",
            message="User account is inactive or missing",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    token_response, new_raw_refresh = _issue_tokens(
        db,
        user=user,
        settings=settings,
        family_id=existing.family_id,
    )
    new_record = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(new_raw_refresh))
    )
    existing.revoked_at = now
    if new_record is not None:
        existing.replaced_by_id = new_record.id

    db.commit()
    return token_response, new_raw_refresh


def revoke_refresh_token(
    db: Session,
    *,
    raw_refresh_token: str | None,
    ip_address: str | None = None,
) -> None:
    """Revoke a refresh token on logout."""
    if not raw_refresh_token:
        return

    token_digest = hash_token(raw_refresh_token)
    existing = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_digest))
    if existing is not None and existing.revoked_at is None:
        existing.revoked_at = utc_now()
        record_audit_event(
            db,
            actor_user_id=existing.user_id,
            action="AUTH_LOGOUT",
            resource_type="user",
            resource_id=str(existing.user_id),
            ip_address=ip_address,
        )
        db.commit()

