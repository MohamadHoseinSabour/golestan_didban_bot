"""Persian text utilities."""
from __future__ import annotations

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
