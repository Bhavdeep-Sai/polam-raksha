import asyncio
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.db.session import get_db, get_session_factory
from app.modules.auctions.router import _authenticate_ws_user
from app.modules.auth.dependencies import get_current_user
from app.modules.notifications.schemas import NotificationResponse
from app.modules.notifications.service import (
    acknowledge_notification,
    list_user_notifications,
)
from app.modules.users.models import User

router = APIRouter(prefix="/notifications", tags=["notifications"])
ws_router = APIRouter(tags=["notifications-ws"])


@router.get(
    "",
    response_model=list[NotificationResponse],
    summary="List current user notifications",
)
def get_my_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[NotificationResponse]:
    rows = list_user_notifications(db, user_id=current_user.id)
    return [NotificationResponse.model_validate(r, from_attributes=True) for r in rows]


@router.post(
    "/{notification_id}/acknowledge",
    response_model=NotificationResponse,
    summary="Acknowledge and mark a notification as read",
)
def ack_my_notification(
    notification_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> NotificationResponse:
    row = acknowledge_notification(db, user_id=current_user.id, notification_id=notification_id)
    return NotificationResponse.model_validate(row, from_attributes=True)


@ws_router.websocket("/ws/notifications")
async def notifications_websocket(
    websocket: WebSocket,
    token: str | None = Query(default=None),
) -> None:
    user = _authenticate_ws_user(token)
    if user is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    session_factory = get_session_factory()
    last_count = -1
    try:
        while True:
            with session_factory() as db:
                items = list_user_notifications(db, user_id=user.id, limit=25)
                if len(items) != last_count:
                    last_count = len(items)
                    await websocket.send_json(
                        {
                            "event_type": "NOTIFICATIONS_SNAPSHOT",
                            "items": [
                                NotificationResponse.model_validate(
                                    r, from_attributes=True
                                ).model_dump(mode="json")
                                for r in items
                            ],
                        }
                    )
            await asyncio.sleep(1.5)
    except WebSocketDisconnect:
        return

