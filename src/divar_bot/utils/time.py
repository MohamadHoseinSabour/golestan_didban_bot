"""Time utilities for the bot."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytz

TEHRAN_TZ = pytz.timezone("Asia/Tehran")


def now_tehran() -> datetime:
    """Current time in Tehran timezone."""
    return datetime.now(tz=TEHRAN_TZ)


def to_tehran(dt: datetime) -> datetime:
    """Convert any aware datetime to Tehran timezone."""
    return dt.astimezone(TEHRAN_TZ)


def relative_time(dt: datetime) -> str:
    """Return a Persian relative time string like '۵ دقیقه پیش'."""
    from divar_bot.utils.persian import to_persian_digits

    now = datetime.now(tz=UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    delta = now - dt.astimezone(UTC)

    if delta < timedelta(0):
        return "همین الان"
    if delta < timedelta(minutes=1):
        secs = int(delta.total_seconds())
        return f"{to_persian_digits(secs)} ثانیه پیش"
    if delta < timedelta(hours=1):
        mins = int(delta.total_seconds() // 60)
        return f"{to_persian_digits(mins)} دقیقه پیش"
    if delta < timedelta(days=1):
        hours = int(delta.total_seconds() // 3600)
        return f"{to_persian_digits(hours)} ساعت پیش"
    days = delta.days
    return f"{to_persian_digits(days)} روز پیش"


def format_time_tehran(dt: datetime) -> str:
    """Format datetime as HH:MM (Tehran) with Persian digits."""
    from divar_bot.utils.persian import to_persian_digits

    tehran_dt = to_tehran(dt)
    hhmm = tehran_dt.strftime("%H:%M")
    return to_persian_digits(hhmm)


def parse_unix_timestamp(ts: int | float | str | None) -> datetime | None:
    """Parse a Unix timestamp (seconds) to UTC-aware datetime."""
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(float(ts), tz=UTC)
    except (ValueError, OSError, OverflowError):
        return None


def is_too_old(dt: datetime | None, max_age_minutes: int) -> bool:
    """Return True if dt is older than max_age_minutes."""
    if dt is None:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    age = datetime.now(tz=UTC) - dt.astimezone(UTC)
    return age > timedelta(minutes=max_age_minutes)
