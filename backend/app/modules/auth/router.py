import hmac
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Header, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.security import generate_opaque_token
from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import (
    LoginRequest,
    LogoutResponse,
    PinLoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserSummary,
)
from app.modules.auth.service import (
    authenticate_password,
    authenticate_pin,
    register_user,
    revoke_refresh_token,
    rotate_refresh_token,
)
from app.modules.users.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "polam_refresh_token"
CSRF_COOKIE_NAME = "polam_csrf_token"


def _set_auth_cookies(response: Response, raw_refresh: str, settings: Settings) -> None:
    max_age = settings.jwt_refresh_token_expire_days * 86400
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_refresh,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=max_age,
        path=f"{settings.api_v1_prefix}/auth",
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=generate_opaque_token(),
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=max_age,
        path=f"{settings.api_v1_prefix}/auth",
    )


def _clear_auth_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path=f"{settings.api_v1_prefix}/auth")
    response.delete_cookie(key=CSRF_COOKIE_NAME, path=f"{settings.api_v1_prefix}/auth")


def _verify_csrf_for_cookie(
    cookie_token: str | None,
    csrf_cookie: str | None,
    csrf_header: str | None,
) -> None:
    if cookie_token is None:
        return
    if not csrf_cookie or not csrf_header or not hmac.compare_digest(csrf_cookie, csrf_header):
        raise AppError(
            code="csrf_validation_failed",
            message="CSRF token missing or invalid for cookie-authenticated request",
            status_code=status.HTTP_403_FORBIDDEN,
        )


@router.post(
    "/register",
    response_model=UserSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new farmer or buyer account",
)
def register(
    payload: RegisterRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> UserSummary:
    ip = request.client.host if request.client else None
    return register_user(db, payload=payload, ip_address=ip)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate with email/phone and password",
)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    ip = request.client.host if request.client else None
    token_response, raw_refresh = authenticate_password(
        db,
        identifier=payload.identifier,
        password=payload.password,
        settings=settings,
        ip_address=ip,
    )
    _set_auth_cookies(response, raw_refresh, settings)
    return token_response


@router.post(
    "/pin-login",
    response_model=TokenResponse,
    summary="Authenticate keypad phone user with phone number and PIN",
)
def pin_login(
    payload: PinLoginRequest,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    ip = request.client.host if request.client else None
    token_response, raw_refresh = authenticate_pin(
        db,
        phone_number=payload.phone_number,
        pin=payload.pin,
        settings=settings,
        ip_address=ip,
    )
    _set_auth_cookies(response, raw_refresh, settings)
    return token_response


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate refresh token and issue a new access token",
)
def refresh(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    payload: RefreshRequest | None = None,
    polam_refresh_token: Annotated[str | None, Cookie()] = None,
    polam_csrf_token: Annotated[str | None, Cookie()] = None,
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> TokenResponse:
    if polam_refresh_token is not None:
        _verify_csrf_for_cookie(polam_refresh_token, polam_csrf_token, x_csrf_token)
        raw_token = polam_refresh_token
    elif payload and payload.refresh_token:
        raw_token = payload.refresh_token
    else:
        raise AppError(
            code="missing_refresh_token",
            message="Refresh token was not provided",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    ip = request.client.host if request.client else None
    token_response, new_raw_refresh = rotate_refresh_token(
        db,
        raw_refresh_token=raw_token,
        settings=settings,
        ip_address=ip,
    )
    _set_auth_cookies(response, new_raw_refresh, settings)
    return token_response


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Revoke refresh token and clear auth cookies",
)
def logout(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    payload: RefreshRequest | None = None,
    polam_refresh_token: Annotated[str | None, Cookie()] = None,
    polam_csrf_token: Annotated[str | None, Cookie()] = None,
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> LogoutResponse:
    if polam_refresh_token is not None:
        _verify_csrf_for_cookie(polam_refresh_token, polam_csrf_token, x_csrf_token)
        raw_token: str | None = polam_refresh_token
    else:
        raw_token = payload.refresh_token if payload else None

    ip = request.client.host if request.client else None
    revoke_refresh_token(db, raw_refresh_token=raw_token, ip_address=ip)
    _clear_auth_cookies(response, settings)
    return LogoutResponse()


@router.get(
    "/me",
    response_model=UserSummary,
    summary="Get the currently authenticated user",
)
def me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserSummary:
    return UserSummary(
        id=current_user.id,
        full_name=current_user.full_name,
        role=current_user.role,
        preferred_language=current_user.preferred_language,
        is_active=current_user.is_active,
    )

