import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    event_id: str
    event_type: str
    channel: str
    status: str
    title: str
    body: str
    provider_message: str | None = None
    metadata_json: dict[str, Any]
    is_read: bool
    delivered_at: datetime | None = None
    acknowledged_at: datetime | None = None
    created_at: datetime

