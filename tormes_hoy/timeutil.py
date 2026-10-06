"""Time helpers. All public timestamps are ISO 8601 with offset."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo


def now_in(tz_name: str) -> datetime:
    """Return the current time in the given IANA time zone."""
    return datetime.now(ZoneInfo(tz_name)).replace(microsecond=0)


def parse_local(value: str, tz_name: str) -> datetime:
    """Parse a naive or aware timestamp, assuming ``tz_name`` if naive.

    Accepts ``YYYY-MM-DDTHH:MM[:SS]`` and ``YYYY-MM-DD HH:MM[:SS]``.
    """
    parsed = datetime.fromisoformat(value.strip().replace(" ", "T"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(tz_name))
    return parsed.astimezone(ZoneInfo(tz_name))


def parse_utc(value: str, tz_name: str) -> datetime:
    """Parse a timestamp that is UTC when naive and convert to ``tz_name``."""
    parsed = datetime.fromisoformat(value.strip().replace(" ", "T"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(ZoneInfo(tz_name))


def iso(value: datetime) -> str:
    """Format a datetime as ISO 8601 with seconds precision."""
    return value.isoformat(timespec="seconds")


def is_older_than(value: datetime, now: datetime, hours: float) -> bool:
    """Return True if ``value`` is more than ``hours`` before ``now``."""
    return now - value > timedelta(hours=hours)
