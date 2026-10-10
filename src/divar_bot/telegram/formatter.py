"""
Telegram message formatter for Divar real-estate notifications.
Implements the exact layout from Section 2.3 of the specification:
- HTML parse mode with proper escaping
- Persian digits and thousand separators
- Tehran timezone
- Clean omission of missing fields (no placeholder strings)
- Dynamic template adaptation for Sell vs Rent vs Land vs Commercial
"""

from __future__ import annotations

import html

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from divar_bot.models import AdCategory, AdDetail
from divar_bot.utils.persian import format_area, format_price, to_persian_digits
from divar_bot.utils.time import format_time_tehran, now_tehran


def escape(text: str | None) -> str:
    """HTML-escape user strings to prevent injection or parse errors."""
    return html.escape(text or "", quote=True)


def format_ad_message(ad: AdDetail) -> tuple[str, InlineKeyboardMarkup]:
    """
    Format an AdDetail into an HTML message string and an inline keyboard button.
    Returns (html_text, inline_markup).
    """
    lines: list[str] = []

    # 1. Header (Category & Type)
    header_cat = "ملک"
    if ad.ad_category == AdCategory.SELL:
        header_cat = "فروش آپارتمان" if (ad.floor is not None or "آپارتمان" in (ad.title or "")) else "فروش ملک"
    elif ad.ad_category == AdCategory.RENT:
        header_cat = "رهن و اجاره" if (ad.mortgage and ad.monthly_rent) else "اجاره ملک"
    elif ad.ad_category == AdCategory.COMMERCIAL:
        header_cat = "تجاری و اداری"
    elif ad.ad_category == AdCategory.LAND:
        header_cat = "زمین و کلنگی"

    lines.append(f"🏠 <b>آگهی جدید شخصی</b> | {header_cat}")
    lines.append("━━━━━━━━━━━━━━")

    # 2. Title
    if ad.title:
        lines.append(f"📌 «{escape(ad.title)}»")

    # 3. Location
    loc_parts: list[str] = []
    if ad.city:
        loc_parts.append(escape("اهواز" if ad.city == "ahvaz" else ad.city))
    if ad.district:
        loc_parts.append(escape(ad.district))
    if loc_parts:
        lines.append(f"📍 منطقه: {' · '.join(loc_parts)}")

    # 4. Publication Time
    time_str = format_time_tehran(ad.created_at or now_tehran())
    if ad.created_at_relative:
        lines.append(f"🕐 انتشار: {time_str} ({escape(ad.created_at_relative)})")
    else:
        lines.append(f"🕐 انتشار: {time_str}")

    # 5. Pricing (Sell vs Rent)
    if ad.ad_category == AdCategory.SELL or (ad.total_price and not ad.mortgage and not ad.monthly_rent):
        if ad.total_price:
            lines.append(f"💰 قیمت کل: <b>{format_price(ad.total_price)}</b>")
        if ad.price_per_m2:
            lines.append(f"💵 متری: {format_price(ad.price_per_m2)}")

    elif ad.ad_category == AdCategory.RENT or (ad.mortgage is not None or ad.monthly_rent is not None):
        if ad.mortgage is not None:
            lines.append(f"💰 ودیعه: <b>{format_price(ad.mortgage)}</b>")
        if ad.monthly_rent is not None:
            lines.append(f"💵 اجاره ماهانه: <b>{format_price(ad.monthly_rent)}</b>")
        if ad.convertible is not None:
            conv_text = "✅ قابل تبدیل" if ad.convertible else "❌ غیر قابل تبدیل"
            lines.append(f"🔄 تبدیل: {conv_text}")

    # Fallback price if uncategorized
    elif ad.total_price:
        lines.append(f"💰 قیمت: <b>{format_price(ad.total_price)}</b>")

    # 6. Specs (Area, Rooms, Year Built)
    specs: list[str] = []
    if ad.area_m2:
        specs.append(f"📐 {format_area(ad.area_m2)}")
    if ad.rooms is not None:
        specs.append(f"🛏 {to_persian_digits(ad.rooms)} خوابه")
    if ad.year_built is not None:
        specs.append(f"🏗 ساخت {to_persian_digits(ad.year_built)}")
    if specs:
        lines.append(" · ".join(specs))

    # 7. Floor
    if ad.floor is not None:
        floor_str = to_persian_digits(ad.floor)
        if ad.total_floors is not None:
            lines.append(f"🏢 طبقه {floor_str} از {to_persian_digits(ad.total_floors)}")
        else:
            lines.append(f"🏢 طبقه {floor_str}")

    # 8. Amenities (Elevator, Parking, Storage)
    amenities: list[str] = []
    if ad.has_elevator is not None:
        amenities.append("✅ آسانسور" if ad.has_elevator else "❌ آسانسور")
    if ad.has_parking is not None:
        amenities.append("✅ پارکینگ" if ad.has_parking else "❌ پارکینگ")
    if ad.has_storage is not None:
        amenities.append("✅ انباری" if ad.has_storage else "❌ انباری")
    if amenities:
        lines.append("  ".join(amenities))

    # 9. Tags / Status
    if ad.tags:
        tags_str = " · ".join(escape(t) for t in ad.tags)
        lines.append(f"🏷 وضعیت: {tags_str}")

    # 10. Contact Phone
    if ad.contact_phones:
        phone_tags = " · ".join(f"<code>{escape(p)}</code>" for p in ad.contact_phones)
        lines.append(f"📞 تماس: {phone_tags}")

    # 11. Link
    lines.append(f"🔗 {ad.divar_url}")

    # Join and ensure max Telegram limit (4096 chars)
    full_text = "\n".join(lines)
    if len(full_text) > 4000:
        full_text = full_text[:3990] + "...\n🔗 " + ad.divar_url

    # Inline button
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 مشاهده در دیوار", url=ad.divar_url)]
    ])

    return full_text, keyboard
