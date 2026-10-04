"""
Two-layer classifier to distinguish personal ads from agency/realtor ads.
Layer 1: Official Divar business metadata (business_type, business_ref, agency badges).
Layer 2: Text heuristics on title and description using agency keywords.
"""

from __future__ import annotations

import re
from typing import Any

from divar_bot.models import ClassifierResult
from divar_bot.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_AGENCY_KEYWORDS = [
    "املاک",
    "مشاور املاک",
    "مشاورین املاک",
    "بنگاه",
    "آژانس املاک",
    "گروه املاک",
    "دپارتمان املاک",
    "مسکن مهر",
    "کارگزاری املاک",
    "دفتر املاک",
]


class AdClassifier:
    """Classifies whether an ad is genuinely personal or from a real-estate agency."""

    def __init__(self, agency_keywords: list[str] | None = None) -> None:
        self.agency_keywords = agency_keywords or DEFAULT_AGENCY_KEYWORDS
        # Compile regex for fast matching
        escaped_words = [re.escape(k) for k in self.agency_keywords]
        self._pattern = re.compile(rf"\b({'|'.join(escaped_words)})\b", re.IGNORECASE)

    def classify(self, detail_data: dict[str, Any]) -> tuple[ClassifierResult, str]:
        """
        Classify an ad from its raw detail JSON.
        Returns (ClassifierResult, reason).
        """
        webengage = detail_data.get("webengage", {}) or {}

        # -------------------------------------------------------------
        # Layer 1: Official Divar metadata
        # -------------------------------------------------------------
        business_type = webengage.get("business_type")
        business_ref = webengage.get("business_ref")

        if business_type and business_type != "personal":
            reason = f"Official business_type is '{business_type}' (not personal)"
            logger.info("classified_agency_by_metadata", reason=reason)
            return ClassifierResult.AGENCY, reason

        if business_ref:
            reason = f"Post has agency business_ref: '{business_ref}'"
            logger.info("classified_agency_by_business_ref", reason=reason)
            return ClassifierResult.AGENCY, reason

        # Check sections for agency or business profile badges
        for section in detail_data.get("sections", []):
            if not isinstance(section, dict):
                continue
            for widget in section.get("widgets", []):
                if not isinstance(widget, dict):
                    continue
                w_data = widget.get("data", {})
                w_type = widget.get("widget_type")
                # Look for business badge or real estate agent profile
                if w_type in ("BUSINESS_SECTION", "BUSINESS_ROW", "AGENT_ROW"):
                    reason = f"Widget '{w_type}' indicates real estate agency"
                    return ClassifierResult.AGENCY, reason
                title = str(w_data.get("title", ""))
                if "مشاور املاک" in title or "آژانس املاک" in title:
                    reason = f"Widget title explicitly mentions agency: '{title}'"
                    return ClassifierResult.AGENCY, reason

        # -------------------------------------------------------------
        # Layer 2: Text heuristics (title & description)
        # -------------------------------------------------------------
        title = ""
        description = ""

        # Extract title from SEO or sections
        title = detail_data.get("seo", {}).get("title", "")
        for section in detail_data.get("sections", []):
            sec_name = section.get("section_name")
            if sec_name == "TITLE":
                for w in section.get("widgets", []):
                    if w.get("widget_type") in ("TITLE_ROW", "LEGEND_TITLE_ROW"):
                        title = w.get("data", {}).get("title") or w.get("data", {}).get("text") or title
            elif sec_name == "DESCRIPTION":
                for w in section.get("widgets", []):
                    if w.get("widget_type") == "DESCRIPTION_ROW":
                        description = w.get("data", {}).get("text", "")

        text_to_scan = f"{title} {description}"

        for kw in self.agency_keywords:
            if kw in text_to_scan:
                reason = f"Keyword match: '{kw}' found in title or description"
                logger.info("classified_agency_by_keyword", keyword=kw, reason=reason)
                return ClassifierResult.AGENCY, reason

        # If business_type is explicitly personal and passed keyword checks
        if business_type == "personal":
            return ClassifierResult.PERSONAL, "Official personal status verified with no agency keywords"

        return ClassifierResult.PERSONAL, "No agency signs detected"
