"""Single source of truth for timestamps.

Storage convention: DATETIME columns hold NAIVE UTC values. SQLite stores
datetimes as text, the API serializes them without a UTC offset, and the
frontend appends 'Z' when parsing — so the naive-UTC convention must be
preserved end to end. These helpers keep that convention while sourcing
time from the timezone-aware clock, replacing the deprecated
datetime.utcnow() / datetime.utcfromtimestamp() (Python 3.12+).

Import this module instead of calling datetime.utcnow() anywhere.
"""
from datetime import datetime, timezone


def utc_now() -> datetime:
    """Current UTC time as a naive datetime (storage convention)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utc_from_timestamp(ts: float) -> datetime:
    """Convert an epoch timestamp to a naive UTC datetime (storage convention)."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
