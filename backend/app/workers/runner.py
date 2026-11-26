import logging
import signal
import time
from types import FrameType

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import get_session_factory
from app.workers.jobs import process_due_jobs

logger = logging.getLogger(__name__)
_running = True


def _handle_shutdown(signum: int, _frame: FrameType | None) -> None:
    global _running
    logger.info("Worker received shutdown signal (%s); stopping...", signum)
    _running = False


def run_worker() -> None:
    """Run the PolamRaksha background worker loop processing persistent scheduled jobs."""
    settings = get_settings()
    configure_logging(settings.log_level)

    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    logger.info(
        "PolamRaksha worker started (env=%s, interval=%ss)",
        settings.app_env,
        settings.worker_poll_interval_seconds,
    )

    session_factory = get_session_factory()
    while _running:
        try:
            with session_factory() as db:
                processed = process_due_jobs(db)
                if processed > 0:
                    logger.info("Worker processed %d due jobs", processed)
        except SQLAlchemyError as exc:
            logger.warning("Worker job cycle failed: %s", exc)

        time.sleep(settings.worker_poll_interval_seconds)

    logger.info("PolamRaksha worker stopped")


if __name__ == "__main__":
    run_worker()
