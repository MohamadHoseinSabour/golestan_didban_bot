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


def parse_relative_age_minutes(text: str | None) -> int | None:
    """
    Parse a Persian relative time string into elapsed minutes.
    Examples:
      '۵ دقیقه پیش' -> 5
      '۱ ساعت پیش' -> 60
      '۳ روز پیش' -> 4320
      '۲ ماه پیش' -> 86400
      'سال پیش' -> 525600
    """
    if not text:
        return None
    import re

    fa_to_en = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
    cleaned = text.strip().translate(fa_to_en)

    m_num = re.search(r"(\d+)", cleaned)
    num = int(m_num.group(1)) if m_num else 1

    if "ثانیه" in cleaned or "لحظات" in cleaned:
        return 1
    if "دقیقه" in cleaned:
        if "نیم" in cleaned:
            return 30
        return num
    if "ساعت" in cleaned:
        if "نیم" in cleaned:
            return 30
        return num * 60
    if "دیروز" in cleaned:
        return 24 * 60
    if "پریروز" in cleaned:
        return 48 * 60
    if "روز" in cleaned:
        return num * 24 * 60
    if "هفته" in cleaned:
        return num * 7 * 24 * 60
    if "ماه" in cleaned:
        return num * 30 * 24 * 60
    if "سال" in cleaned or "پارسال" in cleaned:
        return num * 365 * 24 * 60

    return None


def parse_relative_time_to_datetime(text: str | None) -> datetime | None:
    """Convert Persian relative time string to an approximate UTC datetime."""
    minutes = parse_relative_age_minutes(text)
    if minutes is None:
        return None
    return datetime.now(tz=UTC) - timedelta(minutes=minutes)


def is_too_old(dt: datetime | None, max_age_minutes: int) -> bool:
    """Return True if dt is older than max_age_minutes."""
    if dt is None:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    age = datetime.now(tz=UTC) - dt.astimezone(UTC)
    return age > timedelta(minutes=max_age_minutes)
