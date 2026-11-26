from datetime import UTC, datetime, timedelta, timezone

IST_TIMEZONE = timezone(timedelta(hours=5, minutes=30), name="IST")


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(UTC)


def to_ist(dt: datetime) -> datetime:
    """Convert a timezone-aware datetime to IST (+05:30)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(IST_TIMEZONE)

