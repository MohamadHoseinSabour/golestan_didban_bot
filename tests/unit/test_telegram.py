"""
Unit tests for Telegram formatter and security modules.
"""
from datetime import UTC, datetime

from divar_bot.models import AdCategory, AdDetail, AdImage
from divar_bot.telegram.formatter import format_ad_message
from divar_bot.telegram.security import is_user_allowed


def test_is_user_allowed():
    allowed_list = [275352822, 1069082757]
    assert is_user_allowed(275352822, allowed_list) is True
    assert is_user_allowed(1069082757, allowed_list) is True
    assert is_user_allowed("275352822", allowed_list) is True
    assert is_user_allowed(99999, allowed_list) is False
    assert is_user_allowed(None, allowed_list) is False
    assert is_user_allowed(275352822, []) is False

    # Callable allowed_ids
    assert is_user_allowed(1069082757, lambda: allowed_list) is True
    assert is_user_allowed(99999, lambda: allowed_list) is False



def test_format_ad_sell_apartment():
    ad = AdDetail(
        token="test_token_123",
        title="آپارتمان ۹۵ متری گلستان",
        url="https://divar.ir/v/test_token_123",
        city="ahvaz",
        district="گلستان",
        created_at=datetime(2026, 10, 5, 14, 30, tzinfo=UTC),
        created_at_relative="۵ دقیقه پیش",
        ad_category=AdCategory.SELL,
        total_price=3200000000,
        price_per_m2=33684000,
        area_m2=95.0,
        rooms=2,
        year_built=1400,
        floor=3,
        total_floors=5,
        has_elevator=True,
        has_parking=True,
        has_storage=False,
        tags=["فوری"],
        images=[AdImage(url="https://example.com/img.jpg")],
    )

    text, keyboard = format_ad_message(ad)
    assert "آگهی جدید شخصی" in text
    assert "فروش آپارتمان" in text
    assert "«آپارتمان ۹۵ متری گلستان»" in text
    assert "اهواز · گلستان" in text
    assert "۳٬۲۰۰٬۰۰۰٬۰۰۰ تومان" in text
    assert "۳۳٬۶۸۴٬۰۰۰ تومان" in text
    assert "۹۵ متر" in text
    assert "۲ خوابه" in text
    assert "ساخت ۱۴۰۰" in text
    assert "طبقه ۳ از ۵" in text
    assert "✅ آسانسور" in text
    assert "✅ پارکینگ" in text
    assert "❌ انباری" in text
    assert "فوری" in text
    assert "https://divar.ir/v/test_token_123" in text
    assert keyboard.inline_keyboard[0][0].url == "https://divar.ir/v/test_token_123"


def test_format_ad_rent_omits_missing_fields():
    # Ad without rooms, floor, elevator, or storage
    ad = AdDetail(
        token="rent_456",
        title="رهن واحد مسکونی",
        url="https://divar.ir/v/rent_456",
        city="ahvaz",
        district="گلستان",
        ad_category=AdCategory.RENT,
        mortgage=500000000,
        monthly_rent=5000000,
        convertible=True,
        area_m2=80.0,
        # No rooms, no elevator, no parking
    )

    text, keyboard = format_ad_message(ad)
    assert "رهن و اجاره" in text
    assert "۵۰۰٬۰۰۰٬۰۰۰ تومان" in text
    assert "۵٬۰۰۰٬۰۰۰ تومان" in text
    assert "✅ قابل تبدیل" in text
    assert "۸۰ متر" in text
    # Ensure missing fields are NOT rendered with placeholder strings
    assert "خوابه" not in text
    assert "طبقه" not in text
    assert "آسانسور" not in text
    assert "نامشخص" not in text
