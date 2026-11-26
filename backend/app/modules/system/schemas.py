from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Liveness probe response."""

    status: Literal["ok"]
    service: str
    environment: str
    timestamp_utc: datetime


class ReadinessResponse(BaseModel):
    """Readiness probe response including database connectivity."""

    status: Literal["ready", "not_ready"]
    database: Literal["connected", "disconnected"]
    timestamp_utc: datetime

