from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.modules.system.schemas import HealthResponse, ReadinessResponse
from app.modules.system.service import get_health_status, get_readiness_status

router = APIRouter(tags=["system"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service liveness check",
)
def health_check(
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthResponse:
    """Return basic liveness status without external dependencies."""
    return get_health_status(settings)


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Service readiness check",
)
def readiness_check(
    db: Annotated[Session, Depends(get_db)],
) -> ReadinessResponse:
    """Verify PostgreSQL connectivity for readiness probes."""
    return get_readiness_status(db)

