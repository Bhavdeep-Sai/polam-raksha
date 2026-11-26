from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.analytics.schemas import ImpactAnalyticsResponse
from app.modules.analytics.service import get_impact_analytics
from app.modules.auth.dependencies import require_roles
from app.modules.users.models import User, UserRole

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get(
    "/impact",
    response_model=ImpactAnalyticsResponse,
    summary="Get timezone-aware impact analytics (production separated from simulated demo data)",
)
def impact_analytics(
    _user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR))],
    db: Annotated[Session, Depends(get_db)],
    start_date: Annotated[date | None, Query(description="Start date in IST (YYYY-MM-DD)")] = None,
    end_date: Annotated[date | None, Query(description="End date in IST (YYYY-MM-DD)")] = None,
    crop_code: Annotated[str | None, Query()] = None,
    location: Annotated[str | None, Query()] = None,
    include_simulated: Annotated[bool, Query()] = False,
) -> ImpactAnalyticsResponse:
    return get_impact_analytics(
        db,
        start_date=start_date,
        end_date=end_date,
        crop_code=crop_code,
        location=location,
        include_simulated=include_simulated,
    )
