import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.modules.auth.dependencies import require_roles
from app.modules.demo.service import (
    advance_demo_auction_and_allocate,
    ensure_demo_mode,
    record_demo_collection,
    reset_demo_only_data,
    simulate_demo_bids,
    simulate_demo_cancellation_and_recovery,
    start_demo_scenario,
)
from app.modules.users.models import User, UserRole

router = APIRouter(prefix="/admin/demo", tags=["admin-demo"])


class DemoAuctionActionRequest(BaseModel):
    auction_id: uuid.UUID


@router.get("/status", summary="Check whether demo mode is enabled")
def demo_status(
    _admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    ensure_demo_mode(settings)
    return {
        "demo_mode_enabled": settings.demo_mode_enabled,
        "app_env": settings.app_env,
        "demo_auction_duration_seconds": settings.demo_auction_duration_seconds,
    }


@router.post("/scenario/start", summary="Start 300 kg Tomato demo scenario")
def demo_start(
    admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    ensure_demo_mode(settings)
    return start_demo_scenario(db, admin=admin, settings=settings)


@router.post("/scenario/simulate-bids", summary="Simulate 3+ competitive buyer bids")
def demo_bids(
    payload: DemoAuctionActionRequest,
    admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    ensure_demo_mode(settings)
    return simulate_demo_bids(db, admin=admin, auction_id=payload.auction_id)


@router.post("/scenario/advance-allocate", summary="Close demo auction & run CP-SAT allocation")
def demo_advance_allocate(
    payload: DemoAuctionActionRequest,
    admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    ensure_demo_mode(settings)
    return advance_demo_auction_and_allocate(db, admin=admin, auction_id=payload.auction_id)


@router.post(
    "/scenario/simulate-cancellation",
    summary="Simulate buyer cancellation & standby recovery allocation",
)
def demo_cancel_recover(
    payload: DemoAuctionActionRequest,
    admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    ensure_demo_mode(settings)
    return simulate_demo_cancellation_and_recovery(
        db, admin=admin, auction_id=payload.auction_id
    )


@router.post("/scenario/record-collection", summary="Record simulated collection for analytics")
def demo_collect(
    payload: DemoAuctionActionRequest,
    admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    ensure_demo_mode(settings)
    return record_demo_collection(db, admin=admin, auction_id=payload.auction_id)


@router.post("/scenario/reset", summary="Reset ONLY simulated demo records")
def demo_reset(
    admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    ensure_demo_mode(settings)
    return reset_demo_only_data(db, admin=admin)

