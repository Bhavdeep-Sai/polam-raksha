from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import status

from app.core.errors import AppError

UrgencyOption = Literal["WITHIN_2H", "WITHIN_6H", "WITHIN_12H", "WITHIN_24H", "CUSTOM"]

MIN_FEASIBLE_WINDOW = timedelta(minutes=60)


@dataclass(frozen=True)
class DeadlineSchedule:
    """Authoritative deadline schedule computed from collection urgency."""

    urgency_option: UrgencyOption
    is_direct_offer_mode: bool
    auction_opens_at: datetime
    initial_bidding_close_at: datetime
    hard_bidding_close_at: datetime
    farmer_approval_deadline_at: datetime
    buyer_confirmation_deadline_at: datetime
    recovery_deadline_at: datetime
    collection_deadline_at: datetime


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def compute_deadline_schedule(
    *,
    now: datetime,
    urgency_option: UrgencyOption,
    custom_collection_deadline_at: datetime | None = None,
) -> DeadlineSchedule:
    """Calculate a feasible auction, approval, recovery, and collection schedule."""
    now_utc = _ensure_utc(now)

    urgency_deltas: dict[str, timedelta] = {
        "WITHIN_2H": timedelta(hours=2),
        "WITHIN_6H": timedelta(hours=6),
        "WITHIN_12H": timedelta(hours=12),
        "WITHIN_24H": timedelta(hours=24),
    }

    if urgency_option == "CUSTOM":
        if custom_collection_deadline_at is None:
            raise AppError(
                code="missing_custom_deadline",
                message="custom_collection_deadline_at is required when urgency_option is CUSTOM",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        collection_deadline = _ensure_utc(custom_collection_deadline_at)
    else:
        collection_deadline = now_utc + urgency_deltas[urgency_option]

    if collection_deadline <= now_utc:
        raise AppError(
            code="expired_collection_deadline",
            message="Collection deadline must be in the future",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    total_window = collection_deadline - now_utc
    if total_window < MIN_FEASIBLE_WINDOW:
        raise AppError(
            code="infeasible_deadline_schedule",
            message=(
                "At least 60 minutes are required before collection deadline to run "
                "bidding, confirmation, and pickup."
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    auction_opens_at = now_utc

    if total_window <= timedelta(hours=2):
        is_direct_offer_mode = True
        initial_bidding_close_at = now_utc + timedelta(minutes=15)
        hard_bidding_close_at = now_utc + timedelta(minutes=25)
        remaining = collection_deadline - hard_bidding_close_at
        collection_buffer = max(timedelta(minutes=15), remaining // 2)
        post_bid_window = remaining - collection_buffer
    else:
        is_direct_offer_mode = False
        collection_buffer = min(timedelta(hours=2), total_window // 4)
        post_bid_window = min(timedelta(minutes=90), total_window // 4)
        hard_bidding_close_at = collection_deadline - collection_buffer - post_bid_window
        bidding_duration = hard_bidding_close_at - auction_opens_at
        initial_bidding_close_at = auction_opens_at + (bidding_duration * 3) // 4

    farmer_approval_deadline_at = hard_bidding_close_at + (post_bid_window // 3)
    buyer_confirmation_deadline_at = hard_bidding_close_at + ((post_bid_window * 2) // 3)
    recovery_deadline_at = hard_bidding_close_at + post_bid_window

    return DeadlineSchedule(
        urgency_option=urgency_option,
        is_direct_offer_mode=is_direct_offer_mode,
        auction_opens_at=auction_opens_at,
        initial_bidding_close_at=initial_bidding_close_at,
        hard_bidding_close_at=hard_bidding_close_at,
        farmer_approval_deadline_at=farmer_approval_deadline_at,
        buyer_confirmation_deadline_at=buyer_confirmation_deadline_at,
        recovery_deadline_at=recovery_deadline_at,
        collection_deadline_at=collection_deadline,
    )

