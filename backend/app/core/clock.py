from datetime import UTC, datetime, timedelta


def utcnow() -> datetime:
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    """Stored datetimes can come back without a timezone. They are always UTC, so label them."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


IST = timedelta(hours=5, minutes=30)


def local_time(value: datetime) -> str:
    """Campus local time as HH:MM, which is how people read times."""
    return (ensure_utc(value) + IST).strftime("%H:%M")
