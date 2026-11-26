import asyncio
import uuid
from datetime import datetime
from typing import Annotated

import jwt
from fastapi import (
    APIRouter,
    Depends,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db, get_session_factory
from app.modules.auctions.schemas import (
    AuctionDetailResponse,
    AuctionEventEnvelope,
    PlaceBidRequest,
)
from app.modules.auctions.service import (
    get_auction_detail,
    list_open_auctions,
    place_or_revise_bid,
)
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.system.models import TransactionalOutboxEvent
from app.modules.users.models import User, UserRole
from app.shared.time import utc_now

router = APIRouter(prefix="/auctions", tags=["auctions"])
ws_router = APIRouter(tags=["auctions-ws"])


@router.get(
    "",
    response_model=list[AuctionDetailResponse],
    summary="List open and closing auctions",
)
def get_open_auctions(
    db: Annotated[Session, Depends(get_db)],
) -> list[AuctionDetailResponse]:
    return list_open_auctions(db)


@router.get(
    "/{auction_id}",
    response_model=AuctionDetailResponse,
    summary="Get authoritative auction snapshot and eligible offers",
)
def get_auction(
    auction_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AuctionDetailResponse:
    return get_auction_detail(db, auction_id=auction_id, current_user=current_user)


@router.post(
    "/{auction_id}/bids",
    response_model=AuctionDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Place or revise a competitive bid (buyer only, transactional & idempotent)",
)
def submit_bid(
    auction_id: uuid.UUID,
    payload: PlaceBidRequest,
    request: Request,
    buyer: Annotated[User, Depends(require_roles(UserRole.BUYER))],
    db: Annotated[Session, Depends(get_db)],
) -> AuctionDetailResponse:
    ip = request.client.host if request.client else None
    return place_or_revise_bid(
        db,
        auction_id=auction_id,
        buyer=buyer,
        payload=payload,
        ip_address=ip,
    )


def _authenticate_ws_user(token: str | None) -> User | None:
    if not token:
        return None
    settings = get_settings()
    try:
        from app.core.security import decode_access_token

        payload = decode_access_token(token, settings)
        user_id = uuid.UUID(str(payload["sub"]))
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None

    with get_session_factory()() as db:
        user = db.scalar(select(User).where(User.id == user_id))
        if user is None or not user.is_active:
            return None
        return user


@ws_router.websocket("/ws/auctions/{auction_id}")
async def auction_updates_ws(
    websocket: WebSocket,
    auction_id: uuid.UUID,
    token: Annotated[str | None, Query()] = None,
) -> None:
    """Authenticated WebSocket stream backed by outbox polling (single-process MVP)."""
    user = _authenticate_ws_user(token)
    if user is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    last_seen_at: datetime = utc_now()

    try:
        with get_session_factory()() as db:
            snapshot = get_auction_detail(db, auction_id=auction_id, current_user=user)
            last_seen_at = snapshot.server_time_utc
            envelope = AuctionEventEnvelope(
                event_id=uuid.uuid4(),
                event_type="AUCTION_SNAPSHOT",
                auction_id=auction_id,
                server_timestamp=snapshot.server_time_utc,
                entity_version=snapshot.version,
                payload=snapshot.model_dump(mode="json"),
            )
        await websocket.send_json(envelope.model_dump(mode="json"))

        while True:
            await asyncio.sleep(0.5)
            with get_session_factory()() as db:
                events = db.scalars(
                    select(TransactionalOutboxEvent)
                    .where(
                        TransactionalOutboxEvent.aggregate_type == "auction",
                        TransactionalOutboxEvent.aggregate_id == auction_id,
                        TransactionalOutboxEvent.created_at > last_seen_at,
                    )
                    .order_by(TransactionalOutboxEvent.created_at.asc())
                ).all()

                for ev in events:
                    last_seen_at = ev.created_at
                    out_env = AuctionEventEnvelope(
                        event_id=ev.id,
                        event_type=ev.event_type,
                        auction_id=auction_id,
                        server_timestamp=ev.created_at,
                        entity_version=int(ev.payload_json.get("entity_version", 1)),
                        payload=ev.payload_json,
                    )
                    await websocket.send_json(out_env.model_dump(mode="json"))
    except WebSocketDisconnect:
        return
    except Exception:
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
