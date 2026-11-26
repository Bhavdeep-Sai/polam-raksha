import logging

from fastapi import status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.db.session import check_db_connection
from app.modules.system.schemas import HealthResponse, ReadinessResponse
from app.shared.time import utc_now

logger = logging.getLogger(__name__)


def get_health_status(settings: Settings) -> HealthResponse:
    """Return service liveness metadata."""
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        environment=settings.app_env,
        timestamp_utc=utc_now(),
    )


def get_readiness_status(db: Session) -> ReadinessResponse:
    """Verify database readiness or raise a 503 AppError."""
    try:
        check_db_connection(db)
    except SQLAlchemyError as exc:
        logger.warning("Database readiness check failed: %s", exc)
        raise AppError(
            code="database_unavailable",
            message="Database connection is not ready",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from exc

    return ReadinessResponse(
        status="ready",
        database="connected",
        timestamp_utc=utc_now(),
    )

