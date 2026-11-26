import hashlib
import secrets
import uuid
from datetime import timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import Settings
from app.modules.users.models import UserRole
from app.shared.time import utc_now

_password_hasher = PasswordHasher()


def hash_secret(plain: str) -> str:
    """Hash a password or PIN using Argon2id."""
    return _password_hasher.hash(plain)


def verify_secret(plain: str, hashed: str) -> bool:
    """Verify a plaintext password or PIN against an Argon2 hash."""
    try:
        return _password_hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False


def generate_opaque_token() -> str:
    """Generate a cryptographically random URL-safe token."""
    return secrets.token_urlsafe(48)


def hash_token(raw_token: str) -> str:
    """Compute SHA-256 hex digest of an opaque refresh token for storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_access_token(
    *,
    user_id: uuid.UUID,
    role: UserRole,
    settings: Settings,
) -> tuple[str, int]:
    """Create a short-lived signed JWT access token."""
    now = utc_now()
    expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    expires_at = now + expires_delta
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role.value,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, int(expires_delta.total_seconds())


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    """Decode and validate a JWT access token."""
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Invalid token type")
    return dict(payload)

