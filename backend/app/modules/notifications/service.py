import logging
import uuid
from datetime import datetime
from typing import Any, Protocol

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.notifications.models import Notification, NotificationStatus
from app.modules.system.models import TransactionalOutboxEvent
from app.shared.time import utc_now

logger = logging.getLogger(__name__)

SUPPORTED_NOTIFICATION_EVENTS = {
    "NEW_ELIGIBLE_LISTING",
    "BID_SUBMITTED",
    "BID_SURPASSED",
    "AUCTION_EXTENDED",
    "AUCTION_CLOSED",
    "FARMER_APPROVAL_REQUIRED",
    "BUYER_CONFIRMATION_REQUIRED",
    "BUYER_CANCELLATION",
    "RECOVERY_OFFER_AVAILABLE",
    "COLLECTION_DEADLINE_APPROACHING",
    "COLLECTION_COMPLETED",
}


class TelephonyNotificationProvider(Protocol):
    """Optional external telephony/SMS notification provider."""

    def send_message(self, *, user_id: uuid.UUID, title: str, body: str) -> tuple[bool, str]:
        """Return (delivered, provider_detail)."""
        ...


def emit_notification_outbox(
    db: Session,
    *,
    event_id: str,
    event_type: str,
    recipient_user_ids: list[uuid.UUID],
    title: str,
    body: str,
    channels: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> TransactionalOutboxEvent:
    """Enqueue a notification event into the transactional outbox inside the caller transaction."""
    outbox = TransactionalOutboxEvent(
        aggregate_type="notification",
        aggregate_id=uuid.uuid4(),
        event_type=event_type,
        payload_json={
            "event_id": event_id,
            "event_type": event_type,
            "recipient_user_ids": [str(uid) for uid in recipient_user_ids],
            "title": title,
            "body": body,
            "channels": channels or ["in_app", "websocket"],
            "metadata": metadata or {},
        },
    )
    db.add(outbox)
    return outbox


def process_notification_outbox(
    db: Session,
    *,
    now: datetime | None = None,
    telephony_provider: TelephonyNotificationProvider | None = None,
    batch_size: int = 50,
) -> int:
    """Process unpublished notification outbox events with event_id deduplication."""
    current_time = now or utc_now()
    events = db.scalars(
        select(TransactionalOutboxEvent)
        .where(
            TransactionalOutboxEvent.aggregate_type == "notification",
            TransactionalOutboxEvent.published_at.is_(None),
        )
        .order_by(TransactionalOutboxEvent.created_at.asc())
        .limit(batch_size)
    ).all()

    created_count = 0
    seen_keys: set[tuple[uuid.UUID, str, str]] = set()
    for ev in events:
        payload = ev.payload_json
        event_id = str(payload.get("event_id") or ev.id)
        event_type = str(payload.get("event_type") or ev.event_type)
        title = str(payload.get("title") or event_type)
        body = str(payload.get("body") or "")
        channels = [str(c) for c in (payload.get("channels") or ["in_app"])]
        metadata = dict(payload.get("metadata") or {})
        raw_recipients = payload.get("recipient_user_ids") or []

        for raw_uid in raw_recipients:
            uid = uuid.UUID(str(raw_uid))
            for channel in channels:
                dedup_key = (uid, event_id, channel)
                if dedup_key in seen_keys:
                    continue
                existing = db.scalar(
                    select(Notification).where(
                        Notification.user_id == uid,
                        Notification.event_id == event_id,
                        Notification.channel == channel,
                    )
                )
                if existing is not None:
                    seen_keys.add(dedup_key)
                    continue
                seen_keys.add(dedup_key)

                notif_status = NotificationStatus.PENDING.value
                delivered_at: datetime | None = None
                provider_message: str | None = None

                if channel == "in_app":
                    notif_status = NotificationStatus.DELIVERED.value
                    delivered_at = current_time
                elif channel == "websocket":
                    notif_status = NotificationStatus.DELIVERED.value
                    delivered_at = current_time
                elif channel == "browser":
                    notif_status = NotificationStatus.PENDING.value
                elif channel == "telephone":
                    if telephony_provider is None:
                        notif_status = NotificationStatus.FAILED.value
                        provider_message = (
                            "Telephone provider not configured; only in-app notification created."
                        )
                    else:
                        ok, detail = telephony_provider.send_message(
                            user_id=uid, title=title, body=body
                        )
                        notif_status = (
                            NotificationStatus.DELIVERED.value
                            if ok
                            else NotificationStatus.FAILED.value
                        )
                        delivered_at = current_time if ok else None
                        provider_message = detail

                db.add(
                    Notification(
                        user_id=uid,
                        event_id=event_id,
                        event_type=event_type,
                        channel=channel,
                        status=notif_status,
                        title=title,
                        body=body,
                        provider_message=provider_message,
                        metadata_json=metadata,
                        is_read=False,
                        delivered_at=delivered_at,
                    )
                )
                created_count += 1

        ev.published_at = current_time

    db.flush()
    return created_count


def list_user_notifications(
    db: Session,
    *,
    user_id: uuid.UUID,
    limit: int = 50,
) -> list[Notification]:
    return list(
        db.scalars(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        ).all()
    )


def acknowledge_notification(
    db: Session,
    *,
    user_id: uuid.UUID,
    notification_id: uuid.UUID,
) -> Notification:
    notif = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
    )
    if notif is None:
        raise AppError(
            code="notification_not_found",
            message="Notification not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    now = utc_now()
    notif.status = NotificationStatus.ACKNOWLEDGED.value
    notif.is_read = True
    notif.acknowledged_at = notif.acknowledged_at or now
    notif.delivered_at = notif.delivered_at or now
    db.commit()
    db.refresh(notif)
    return notif

