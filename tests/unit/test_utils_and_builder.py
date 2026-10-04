"""
Unit tests for URL builder and utilities (Persian and time).
"""
from datetime import UTC, datetime, timedelta

from divar_bot.divar.url_builder import parse_divar_url
from divar_bot.utils.persian import format_area, format_price, normalize_arabic, to_persian_digits
from divar_bot.utils.time import (
    format_time_tehran,
    is_too_old,
    parse_relative_age_minutes,
    parse_relative_time_to_datetime,
    parse_unix_timestamp,
    relative_time,
)


def test_url_builder():
    raw_url = (
        "https://divar.ir/s/ahvaz/real-estate/golestan"
        "?bbox=48.6043%2C31.2658939%2C48.6834793%2C31.3184261"
        "&business-type=personal%2C"
    )
    params = parse_divar_url(raw_url, use_bbox=True)
    assert params.city_slug == "ahvaz"
    assert params.category_slug == "real-estate"
    assert params.neighborhood_slug == "golestan"
    assert params.city_id == "7"
    assert params.district_id == "323"
    assert params.business_type == "personal"
    assert params.bbox == [48.6043, 31.2658939, 48.6834793, 31.3184261]

    payload = params.to_api_payload()
    assert payload["city_ids"] == ["7"]
    assert "bbox" in payload["search_data"]["form_data"]["data"]
    assert "districts" in payload["search_data"]["form_data"]["data"]


def test_persian_utils():
    assert to_persian_digits(12345) == "۱۲۳۴۵"
    assert format_price(10000000) == "۱۰٬۰۰۰٬۰۰۰ تومان"
    assert format_price(None) is None
    assert format_area(150.0) == "۱۵۰ متر"
    assert format_area(150.5) == "۱۵۰.۵ متر"
    assert format_area(None) is None
    assert normalize_arabic("١٢٣ك") == "۱۲۳ک"


def test_time_utils():
    now = datetime.now(tz=UTC)
    assert relative_time(now - timedelta(seconds=10)) == "۱۰ ثانیه پیش"
    assert relative_time(now - timedelta(minutes=5)) == "۵ دقیقه پیش"
    assert relative_time(now - timedelta(hours=2)) == "۲ ساعت پیش"
    assert relative_time(now - timedelta(days=3)) == "۳ روز پیش"

    # parse_unix_timestamp
    parsed = parse_unix_timestamp(1700000000)
    assert parsed is not None
    assert parsed.year == 2023

    # is_too_old
    assert is_too_old(now - timedelta(minutes=10), max_age_minutes=60) is False
    assert is_too_old(now - timedelta(minutes=120), max_age_minutes=60) is True
    assert is_too_old(None, max_age_minutes=60) is False

    # format_time_tehran
    tehran_str = format_time_tehran(now)
    assert len(tehran_str) == 5  # HH:MM


def test_parse_relative_age_minutes():
    """Verify Persian relative strings properly convert to elapsed minutes."""
    assert parse_relative_age_minutes("لحظاتی پیش") == 1
    assert parse_relative_age_minutes("۵ دقیقه پیش") == 5
    assert parse_relative_age_minutes("۱۰ دقیقه پیش") == 10
    assert parse_relative_age_minutes("نیم ساعت پیش") == 30
    assert parse_relative_age_minutes("۱ ساعت پیش") == 60
    assert parse_relative_age_minutes("۳ ساعت پیش") == 180
    assert parse_relative_age_minutes("دیروز") == 1440
    assert parse_relative_age_minutes("پریروز") == 2880
    assert parse_relative_age_minutes("۳ روز پیش") == 4320
    assert parse_relative_age_minutes("هفته پیش") == 10080
    assert parse_relative_age_minutes("۲ هفته پیش") == 20160
    assert parse_relative_age_minutes("ماه پیش") == 43200
    assert parse_relative_age_minutes("۲ ماه پیش") == 86400
    assert parse_relative_age_minutes("سال پیش") == 525600
    assert parse_relative_age_minutes("پارسال") == 525600
    assert parse_relative_age_minutes(None) is None


def test_relative_time_age_filter_integration():
    """Verify that an ad posted 'سال پیش' is marked too old while fresh ads pass."""
    old_dt = parse_relative_time_to_datetime("سال پیش")
    assert old_dt is not None
    assert is_too_old(old_dt, max_age_minutes=180) is True

    month_dt = parse_relative_time_to_datetime("۲ ماه پیش")
    assert month_dt is not None
    assert is_too_old(month_dt, max_age_minutes=180) is True

    day_dt = parse_relative_time_to_datetime("دیروز")
    assert day_dt is not None
    assert is_too_old(day_dt, max_age_minutes=180) is True

    fresh_dt = parse_relative_time_to_datetime("۵ دقیقه پیش")
    assert fresh_dt is not None
    assert is_too_old(fresh_dt, max_age_minutes=180) is False

