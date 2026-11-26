import uuid
from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.modules.users.models import AssistedAccessRelationship, User, UserRole

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    """Validate Bearer JWT and return the authenticated active User."""
    if credentials is None or not credentials.credentials:
        raise AppError(
            code="not_authenticated",
            message="Authentication credentials were not provided",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        payload = decode_access_token(credentials.credentials, settings)
        user_id = uuid.UUID(str(payload["sub"]))
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise AppError(
            code="invalid_token",
            message="Invalid or expired access token",
            status_code=status.HTTP_401_UNAUTHORIZED,
        ) from exc

    user = db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        raise AppError(
            code="inactive_or_missing_user",
            message="Authenticated user is inactive or does not exist",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    return user


def get_optional_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User | None:
    """Return the authenticated active User if a Bearer token is supplied, else None."""
    if credentials is None or not credentials.credentials:
        return None
    return get_current_user(credentials=credentials, db=db, settings=settings)


def require_roles(*allowed_roles: UserRole) -> Callable[[User], User]:
    """Return a FastAPI dependency enforcing that current_user has one of allowed_roles."""

    def _check_role(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role not in allowed_roles:
            raise AppError(
                code="forbidden_role",
                message="You do not have permission to perform this action",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return current_user

    return _check_role


def authorize_farmer_access(
    *,
    farmer_id: uuid.UUID,
    current_user: User,
    db: Session,
) -> User:
    """Enforce farmer ownership or explicit active operator assisted-access."""
    if current_user.role == UserRole.FARMER:
        if current_user.id != farmer_id:
            raise AppError(
                code="forbidden_farmer_resource",
                message="Farmers can only access their own resources",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return current_user

    if current_user.role == UserRole.OPERATOR:
        assignment = db.scalar(
            select(AssistedAccessRelationship).where(
                AssistedAccessRelationship.operator_id == current_user.id,
                AssistedAccessRelationship.farmer_id == farmer_id,
                AssistedAccessRelationship.is_active.is_(True),
            )
        )
        if assignment is None:
            raise AppError(
                code="operator_not_assigned",
                message="Operator is not authorized to assist this farmer",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        farmer = db.scalar(
            select(User).where(User.id == farmer_id, User.role == UserRole.FARMER)
        )
        if farmer is None:
            raise AppError(
                code="farmer_not_found",
                message="Target farmer was not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return farmer

    raise AppError(
        code="forbidden_farmer_access",
        message="Only the farmer or an assigned operator may perform this action",
        status_code=status.HTTP_403_FORBIDDEN,
    )

