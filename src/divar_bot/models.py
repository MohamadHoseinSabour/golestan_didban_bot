"""
Pydantic data models for Divar ads and notifications.
All fields are optional by default — missing data is None, never a placeholder string.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class AdStatus(StrEnum):
    """Status of an ad in our tracking database."""
    SEEN = "seen"
    NOTIFIED = "notified"
    SKIPPED_AGENCY = "skipped_agency"
    SKIPPED_OLD = "skipped_old"
    FAILED = "failed"


class AdCategory(StrEnum):
    """High-level ad category as detected from Divar's category field."""
    SELL = "sell"
    RENT = "rent"
    MORTGAGE = "mortgage"  # رهن کامل
    LAND = "land"
    COMMERCIAL = "commercial"
    OFFICE = "office"
    UNKNOWN = "unknown"


class ClassifierResult(StrEnum):
    """Result of the agency/personal classifier."""
    PERSONAL = "personal"
    AGENCY = "agency"
    UNCERTAIN = "uncertain"


class AdImage(BaseModel):
    """Thumbnail or full image of an ad."""
    url: str
    width: int | None = None
    height: int | None = None


class Ad(BaseModel):
    """
    Normalized representation of a single Divar listing.
    All fields except token are Optional — parser sets them to None if absent.
    """
    # Identity
    token: str
    title: str | None = None
    url: str = Field(default="")

    # Location
    city: str | None = None
    district: str | None = None
    neighborhood: str | None = None

    # Timing
    created_at: datetime | None = None  # timezone-aware, Asia/Tehran
    created_at_relative: str | None = None  # e.g. "۵ دقیقه پیش"

    # Category
    category_slug: str | None = None
    ad_category: AdCategory = AdCategory.UNKNOWN

    # Pricing — sell
    total_price: int | None = None       # Tomans
    price_per_m2: int | None = None      # Tomans per m²
    # Pricing — rent
    mortgage: int | None = None          # ودیعه (Tomans)
    monthly_rent: int | None = None      # اجاره ماهانه (Tomans)
    convertible: bool | None = None      # قابل تبدیل

    # Property details
    area_m2: float | None = None
    rooms: int | None = None
    year_built: int | None = None
    floor: int | None = None
    total_floors: int | None = None
    has_elevator: bool | None = None
    has_parking: bool | None = None
    has_storage: bool | None = None

    # Status tags (فوری، تخفیف‌دار، قابل معاوضه, ...)
    tags: list[str] = Field(default_factory=list)

    # Images
    images: list[AdImage] = Field(default_factory=list)

    # Classifier output
    classifier_result: ClassifierResult = ClassifierResult.UNCERTAIN
    classifier_reason: str | None = None

    # Contact
    contact_phones: list[str] = Field(default_factory=list)

    # Raw data for debugging
    raw_business_type: str | None = None

    @property
    def divar_url(self) -> str:
        return f"https://divar.ir/v/{self.token}"

    @property
    def thumbnail_url(self) -> str | None:
        return self.images[0].url if self.images else None

    @property
    def contact_phone(self) -> str | None:
        """Primary contact phone number if available."""
        return self.contact_phones[0] if self.contact_phones else None


class AdDetail(Ad):
    """Extended ad with full detail fields (from detail API call)."""
    description: str | None = None
    # Additional fields populated from the detail endpoint
    # These extend Ad with data not available in listing view


class Notification(BaseModel):
    """Record of a sent notification."""
    token: str
    chat_id: int
    message_id: int | None = None
    sent_at: datetime
    attempt: int = 1


class CycleStats(BaseModel):
    """Statistics for a single monitoring cycle."""
    cycle_id: int
    started_at: datetime
    ended_at: datetime | None = None
    duration_seconds: float | None = None
    ads_seen: int = 0
    ads_new: int = 0
    ads_personal: int = 0
    ads_sent: int = 0
    ads_skipped_agency: int = 0
    ads_failed: int = 0
    error: str | None = None
