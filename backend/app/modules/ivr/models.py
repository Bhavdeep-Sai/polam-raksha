import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import JSONBType, UtcDateTime
from app.shared.time import utc_now


class IvrSession(Base):
    __tablename__ = "ivr_sessions"
    __table_args__ = (
        Index("ix_ivr_sessions_caller_phone", "caller_phone"),
        Index("ix_ivr_sessions_external_call_id", "external_call_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    caller_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[str] = mapped_column(
        String(30), nullable=False, default="BROWSER_SIMULATOR"
    )
    external_call_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_webhook_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    session_state: Mapped[str] = mapped_column(String(60), nullable=False, default="AUTH_PIN")
    language: Mapped[str] = mapped_column(String(5), nullable=False, default="te")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    draft_json: Mapped[dict[str, Any]] = mapped_column(JSONBType, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, default=utc_now)
    last_activity_at: Mapped[datetime] = mapped_column(
        UtcDateTime, nullable=False, default=utc_now
    )
    expires_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
