import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auctions.models import Auction, AuctionStatus
from app.modules.notifications.service import process_notification_outbox
from app.modules.system.models import ScheduledJob, TransactionalOutboxEvent
from app.shared.time import utc_now

logger = logging.getLogger(__name__)

MAX_JOB_ATTEMPTS = 5


def enqueue_job(
    db: Session,
    *,
    job_type: str,
    payload: dict[str, Any],
    run_at: datetime,
) -> ScheduledJob:
    """Persist a scheduled job in the database inside the active transaction."""
    job = ScheduledJob(
        job_type=job_type,
        payload_json=payload,
        run_at=run_at,
        status="PENDING",
        attempts=0,
    )
    db.add(job)
    return job


def reschedule_auction_close_job(
    db: Session,
    *,
    auction_id: uuid.UUID,
    new_run_at: datetime,
) -> None:
    """Update pending AUCTION_CLOSE job run_at after a soft-close extension."""
    pending_jobs = db.scalars(
        select(ScheduledJob).where(
            ScheduledJob.job_type == "AUCTION_CLOSE",
            ScheduledJob.status == "PENDING",
        )
    ).all()
    target_id = str(auction_id)
    for job in pending_jobs:
        if job.payload_json.get("auction_id") == target_id:
            job.run_at = new_run_at
            return
    enqueue_job(
        db,
        job_type="AUCTION_CLOSE",
        payload={"auction_id": target_id},
        run_at=new_run_at,
    )


def close_auction_idempotent(
    db: Session,
    *,
    auction_id: uuid.UUID,
    now: datetime,
) -> bool:
    """Idempotently close an auction if still open and past ends_at."""
    auction = db.scalar(
        select(Auction).where(Auction.id == auction_id).with_for_update()
    )
    if auction is None:
        return False

    if auction.status not in {AuctionStatus.OPEN, AuctionStatus.CLOSING}:
        return False

    ends_at = (
        auction.ends_at.replace(tzinfo=now.tzinfo)
        if auction.ends_at.tzinfo is None
        else auction.ends_at
    )
    if now < ends_at:
        return False

    auction.status = AuctionStatus.CLOSED
    auction.closed_at = now
    auction.version += 1

    db.add(
        TransactionalOutboxEvent(
            aggregate_type="auction",
            aggregate_id=auction.id,
            event_type="AUCTION_CLOSED",
            payload_json={
                "auction_id": str(auction.id),
                "entity_version": auction.version,
                "status": auction.status.value,
                "closed_at": now.isoformat(),
            },
        )
    )
    enqueue_job(
        db,
        job_type="APPROVAL_DEADLINE",
        payload={"auction_id": str(auction.id)},
        run_at=now + timedelta(minutes=30),
    )
    return True


def _handle_job(db: Session, job: ScheduledJob, now: datetime) -> None:
    if job.job_type == "AUCTION_CLOSE":
        raw_id = job.payload_json.get("auction_id")
        if raw_id:
            close_auction_idempotent(db, auction_id=uuid.UUID(str(raw_id)), now=now)
        return

    if job.job_type in {
        "APPROVAL_DEADLINE",
        "BUYER_CONFIRMATION_TIMEOUT",
        "COLLECTION_DEADLINE",
        "RECOVERY_PROCESS",
    }:
        logger.info("Processed lifecycle job %s (%s)", job.job_type, job.id)
        return

    logger.warning("Unknown scheduled job type: %s", job.job_type)


def process_due_jobs(db: Session, *, now: datetime | None = None, batch_size: int = 20) -> int:
    """Claim and execute due scheduled jobs safely with row-level locking."""
    current_time = now or utc_now()
    query = (
        select(ScheduledJob)
        .where(
            ScheduledJob.status == "PENDING",
            ScheduledJob.run_at <= current_time,
        )
        .order_by(ScheduledJob.run_at.asc())
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    jobs = db.scalars(query).all()
    processed = 0

    for job in jobs:
        job.status = "RUNNING"
        job.attempts += 1
        try:
            _handle_job(db, job, current_time)
            job.status = "COMPLETED"
            processed += 1
        except Exception as exc:
            logger.exception("Scheduled job %s failed: %s", job.id, exc)
            job.last_error = str(exc)
            if job.attempts >= MAX_JOB_ATTEMPTS:
                job.status = "FAILED"
            else:
                job.status = "PENDING"
                job.run_at = current_time + timedelta(seconds=30 * job.attempts)
    process_notification_outbox(db, now=current_time)
    db.commit()
    return processed

