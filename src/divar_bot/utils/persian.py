"""Persian text utilities."""
from __future__ import annotations

import re

_PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_ARABIC_TO_PERSIAN = str.maketrans("١٢٣٤٥٦٧٨٩٠ك", "۱۲۳۴۵۶۷۸۹۰ک")


def to_persian_digits(text: str | int | float) -> str:
    """Convert ASCII digits to Persian digits."""
    return str(text).translate(_PERSIAN_DIGITS)


def format_price(amount: int | None) -> str | None:
    """Format a price in Tomans with Persian digits and thousand separators."""
    if amount is None:
        return None
    formatted = f"{amount:,}".replace(",", "٬")
    return to_persian_digits(formatted) + " تومان"


def format_area(area_m2: float | None) -> str | None:
    """Format area in square meters with Persian digits."""
    if area_m2 is None:
        return None
    if area_m2 == int(area_m2):
        return to_persian_digits(int(area_m2)) + " متر"
    return to_persian_digits(f"{area_m2:.1f}") + " متر"


def normalize_arabic(text: str) -> str:
    """Convert Arabic chars to Persian equivalents."""
    return text.translate(_ARABIC_TO_PERSIAN)


_FA_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

# Precompiled regex for extracting Iranian phone numbers from text
_SEP = r"[\s\-_./\u200c]*"
_PHONE_PATTERN = re.compile(
    rf"(?<!\d)(?:(?:\+98|0098|0){_SEP})?9(?:{_SEP}\d){{9}}(?!\d)|"
    rf"(?<!\d)0{_SEP}[1-8](?:{_SEP}\d){{9}}(?!\d)"
)


def extract_phone_numbers(text: str | None) -> list[str]:
    """
    Extract and normalize Iranian mobile and landline phone numbers from text.
    Handles Persian, Arabic, and English digits, as well as common separators.
    Returns normalized numbers (e.g. '09161234567', '06133731122').
    """
    if not text:
        return []

    # 1. Convert Persian/Arabic digits to ASCII
    normalized = text.translate(_FA_TO_EN)

    results: list[str] = []
    for match in _PHONE_PATTERN.finditer(normalized):
        raw = match.group(0)
        digits = re.sub(r"\D", "", raw)

        # Normalize prefixes
        if digits.startswith("0098"):
            digits = "0" + digits[4:]
        elif digits.startswith("98") and len(digits) == 12:
            digits = "0" + digits[2:]
        elif digits.startswith("9") and len(digits) == 10:
            digits = "0" + digits

        # Validate Iranian standard lengths and prefixes
        if len(digits) == 11 and digits.startswith("09"):
            if digits not in results:
                results.append(digits)
        elif len(digits) == 11 and digits.startswith("0") and digits[1] in "12345678":
            if digits not in results:
                results.append(digits)

    return results
