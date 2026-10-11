"""
Parser for Divar listing and detail API responses.
Normalizes heterogeneous real estate listings into strongly-typed AdDetail models.
Missing fields are always None (never placeholder strings).
"""

from __future__ import annotations

import json
import re
from typing import Any

from divar_bot.models import AdCategory, AdDetail, AdImage
from divar_bot.utils.persian import extract_phone_numbers, normalize_arabic
from divar_bot.utils.time import now_tehran, parse_relative_time_to_datetime

# Persian digit to ASCII mapping for number parsing
_FA_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def _to_ascii_digits(text: str) -> str:
    return text.translate(_FA_TO_EN)


def _extract_int_from_text(text: str | None) -> int | None:
    """Extract first integer from text (e.g. '۲,۵۰۰,۰۰۰,۰۰۰ تومان' -> 2500000000)."""
    if not text:
        return None
    cleaned = _to_ascii_digits(normalize_arabic(text))
    # Remove non-digits
    digits = re.sub(r"[^\d]", "", cleaned)
    if digits:
        try:
            return int(digits)
        except ValueError:
            return None
    return None


def _extract_float_from_text(text: str | None) -> float | None:
    """Extract float from text (e.g. '۱۵۴ متر' -> 154.0)."""
    if not text:
        return None
    cleaned = _to_ascii_digits(normalize_arabic(text))
    m = re.search(r"(\d+(?:\.\d+)?)", cleaned)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


class DivarParser:
    """Parses raw Divar JSON payloads into AdDetail domain models."""

    @staticmethod
    def parse_listing_widget(widget: dict[str, Any]) -> dict[str, Any] | None:
        """Extract quick summary info from a search list widget (POST_ROW)."""
        data = widget.get("data", {})
        token = data.get("token")
        if not token:
            return None

        title = data.get("title")
        image_url = data.get("image_url")
        middle_desc = data.get("middle_description_text")
        bottom_desc = data.get("bottom_description_text")

        return {
            "token": token,
            "title": title,
            "image_url": image_url,
            "middle_desc": middle_desc,
            "bottom_desc": bottom_desc,
        }

    @staticmethod
    def extract_phones_from_contact(contact_data: dict[str, Any]) -> list[str]:
        """Extract phone numbers from Divar contact_info endpoint response."""
        if not contact_data:
            return []
        raw_str = json.dumps(contact_data, ensure_ascii=False)
        return extract_phone_numbers(raw_str)

    @staticmethod
    def parse_detail(
        token: str,
        detail_data: dict[str, Any],
        extra_phones: list[str] | None = None,
    ) -> AdDetail:
        """Parse the complete detail response into an AdDetail model."""
        webengage = detail_data.get("webengage", {}) or {}
        seo = detail_data.get("seo", {}) or {}

        # 1. Title & URL
        title: str | None = seo.get("title")
        description: str | None = None
        created_at_relative: str | None = None
        tags: list[str] = []
        images: list[AdImage] = []

        # 2. Location
        city: str | None = webengage.get("city") or "ahvaz"
        district: str | None = webengage.get("district")

        # 3. Category
        cat_slug: str | None = webengage.get("category") or webengage.get("cat_3") or webengage.get("cat_2")
        ad_category = AdCategory.UNKNOWN
        if cat_slug:
            if "sell" in cat_slug:
                ad_category = AdCategory.SELL
            elif "rent" in cat_slug or "rahn" in cat_slug:
                ad_category = AdCategory.RENT
            elif "commercial" in cat_slug:
                ad_category = AdCategory.COMMERCIAL
            elif "plot" in cat_slug or "land" in cat_slug:
                ad_category = AdCategory.LAND

        # 4. Numeric fields
        total_price: int | None = webengage.get("price") if webengage.get("price", 0) > 0 else None
        mortgage: int | None = webengage.get("credit") if webengage.get("credit", 0) > 0 else None
        monthly_rent: int | None = webengage.get("rent") if webengage.get("rent", 0) > 0 else None
        price_per_m2: int | None = None
        convertible: bool | None = None

        area_m2: float | None = None
        rooms: int | None = None
        year_built: int | None = None
        floor: int | None = None
        total_floors: int | None = None

        has_elevator: bool | None = None
        has_parking: bool | None = None
        has_storage: bool | None = None

        # 5. Extract from sections
        sections = detail_data.get("sections", [])
        for section in sections:
            if not isinstance(section, dict):
                continue
            sec_name = section.get("section_name")
            widgets = section.get("widgets", [])

            # Extract full title and publication relative time from TITLE section
            if sec_name == "TITLE":
                for w in widgets:
                    w_type = w.get("widget_type")
                    w_data = w.get("data", {})
                    if w_type in ("LEGEND_TITLE_ROW", "TITLE_ROW"):
                        title = w_data.get("title") or w_data.get("text") or title
                    elif w_type == "EXPANDABLE_SECTION":
                        # title like "۱ ساعت پیش در اهواز، گلستان، خ اصفهان"
                        exp_title = w_data.get("title", "")
                        if " در " in exp_title:
                            created_at_relative = exp_title.split(" در ")[0].strip()
                        elif any(k in exp_title for k in ("پیش", "دیروز", "لحظات", "ساعت", "روز", "هفته", "ماه", "سال")):
                            created_at_relative = exp_title.strip()
                        if "گلستان" in exp_title and not district:
                            district = "گلستان"

            # Extract full description
            elif sec_name == "DESCRIPTION":
                for w in widgets:
                    if w.get("widget_type") == "DESCRIPTION_ROW":
                        description = w.get("data", {}).get("text")

            # Extract images
            elif sec_name == "IMAGE":
                for w in widgets:
                    w_data = w.get("data", {})
                    # Items in carousel
                    for it in w_data.get("items", []):
                        img_url = it.get("image", {}).get("url") or it.get("src")
                        if img_url:
                            images.append(AdImage(url=img_url))

            # Extract structured list data (specs, prices, features)
            elif sec_name == "LIST_DATA":
                for w in widgets:
                    w_type = w.get("widget_type")
                    w_data = w.get("data", {})

                    if w_type == "GROUP_INFO_ROW":
                        for it in w_data.get("items", []):
                            t_label = it.get("title", "")
                            t_val = it.get("value", "")
                            if "متراژ" in t_label:
                                area_m2 = _extract_float_from_text(t_val)
                            elif "ساخت" in t_label:
                                year_built = _extract_int_from_text(t_val)
                            elif "اتاق" in t_label:
                                rooms = _extract_int_from_text(t_val)

                    elif w_type == "UNEXPANDABLE_ROW":
                        t_label = w_data.get("title", "")
                        t_val = w_data.get("value", "")

                        if "قیمت کل" in t_label and total_price is None:
                            total_price = _extract_int_from_text(t_val)
                        elif "قیمت هر متر" in t_label:
                            price_per_m2 = _extract_int_from_text(t_val)
                        elif "ودیعه" in t_label and "اجاره" not in t_label and mortgage is None:
                            mortgage = _extract_int_from_text(t_val)
                        elif "اجارهٔ ماهانه" in t_label and monthly_rent is None:
                            monthly_rent = _extract_int_from_text(t_val)
                        elif "ودیعه و اجاره" in t_label:
                            if "قابل تبدیل" in t_val:
                                convertible = "غیر" not in t_val
                        elif "طبقه" in t_label:
                            # format like "۳" or "۱ از ۵"
                            if "از" in t_val:
                                parts = t_val.split("از")
                                floor = _extract_int_from_text(parts[0])
                                total_floors = _extract_int_from_text(parts[1])
                            else:
                                floor = _extract_int_from_text(t_val)

                    elif w_type == "GROUP_FEATURE_ROW":
                        for it in w_data.get("items", []):
                            feat_title = it.get("title", "")
                            avail = it.get("available")
                            if "آسانسور" in feat_title:
                                has_elevator = bool(avail)
                            elif "پارکینگ" in feat_title:
                                has_parking = bool(avail)
                            elif "انباری" in feat_title:
                                has_storage = bool(avail)

            # Extract tags
            elif sec_name == "TAGS":
                for w in widgets:
                    for chip in w.get("data", {}).get("chip_list", {}).get("chips", []):
                        chip_text = chip.get("text")
                        if chip_text:
                            tags.append(chip_text)

        # Fallback category determination from pricing if still UNKNOWN
        if ad_category == AdCategory.UNKNOWN:
            if mortgage is not None or monthly_rent is not None:
                ad_category = AdCategory.RENT
            elif total_price is not None:
                ad_category = AdCategory.SELL

        # Calculate price_per_m2 if missing and possible
        if total_price and area_m2 and area_m2 > 0 and price_per_m2 is None:
            price_per_m2 = int(total_price / area_m2)

        # Parse accurate creation datetime from relative Persian string
        created_at_dt = None
        if created_at_relative:
            created_at_dt = parse_relative_time_to_datetime(created_at_relative)
        if created_at_dt is None:
            created_at_dt = now_tehran()

        # Extract contact phone numbers from text and extra_phones
        contact_phones: list[str] = []
        if extra_phones:
            for p in extra_phones:
                if p not in contact_phones:
                    contact_phones.append(p)

        texts_to_search: list[str] = []
        if title:
            texts_to_search.append(title)
        if description:
            texts_to_search.append(description)

        for section in sections:
            if not isinstance(section, dict):
                continue
            for w in section.get("widgets", []):
                w_data = w.get("data", {})
                for key in ("title", "text", "value", "subtitle", "description"):
                    val = w_data.get(key)
                    if isinstance(val, str):
                        texts_to_search.append(val)

        for text in texts_to_search:
            for p in extract_phone_numbers(text):
                if p not in contact_phones:
                    contact_phones.append(p)

        return AdDetail(
            token=token,
            title=title,
            url=f"https://divar.ir/v/{token}",
            city=city,
            district=district or "گلستان",
            neighborhood=district or "گلستان",
            created_at=created_at_dt,
            created_at_relative=created_at_relative,
            category_slug=cat_slug,
            ad_category=ad_category,
            total_price=total_price,
            price_per_m2=price_per_m2,
            mortgage=mortgage,
            monthly_rent=monthly_rent,
            convertible=convertible,
            area_m2=area_m2,
            rooms=rooms,
            year_built=year_built,
            floor=floor,
            total_floors=total_floors,
            has_elevator=has_elevator,
            has_parking=has_parking,
            has_storage=has_storage,
            tags=tags,
            images=images,
            description=description,
            contact_phones=contact_phones,
            raw_business_type=webengage.get("business_type"),
        )
