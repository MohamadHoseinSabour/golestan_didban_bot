"""
URL builder and parser for Divar URLs.
Converts human-facing search URLs into exact Protobuf JSON payloads for api.divar.ir.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

# Well-known static mappings for immediate fast resolution without extra HTTP calls
WELL_KNOWN_CITIES: dict[str, str] = {
    "tehran": "1",
    "karaj": "2",
    "isfahan": "4",
    "shiraz": "6",
    "ahvaz": "7",
    "mashhad": "8",
    "tabriz": "9",
    "qom": "10",
}

WELL_KNOWN_DISTRICTS: dict[tuple[str, str], str] = {
    ("7", "golestan"): "323",
    ("7", "golestan-ahvaz"): "323",
    ("7", "kianpars"): "322",
    ("7", "zeitun-karmandi"): "324",
    ("7", "padadshahr"): "325",
}


class DivarSearchParams:
    """Parsed components of a Divar search URL."""

    def __init__(
        self,
        city_slug: str,
        category_slug: str,
        neighborhood_slug: str | None = None,
        city_id: str | None = None,
        district_id: str | None = None,
        business_type: str | None = "personal",
        bbox: list[float] | None = None,
        use_bbox: bool = True,
    ) -> None:
        self.city_slug = city_slug
        self.category_slug = category_slug
        self.neighborhood_slug = neighborhood_slug
        self.city_id = city_id or WELL_KNOWN_CITIES.get(city_slug, "7")
        self.district_id = district_id or (
            WELL_KNOWN_DISTRICTS.get((self.city_id, neighborhood_slug or ""))
        )
        self.business_type = business_type
        self.bbox = bbox
        self.use_bbox = use_bbox

    def to_api_payload(self, page_size: int = 24) -> dict[str, Any]:
        """Generate the exact protobuf-over-JSON payload for api.divar.ir search."""
        form_data: dict[str, Any] = {
            "category": {"str": {"value": self.category_slug or "real-estate"}},
        }

        if self.business_type:
            form_data["business-type"] = {
                "repeated_string": {"value": [self.business_type]}
            }

        if self.district_id:
            form_data["districts"] = {
                "repeated_string": {"value": [str(self.district_id)]}
            }

        if self.bbox and self.use_bbox and len(self.bbox) == 4:
            form_data["bbox"] = {
                "repeated_float": {
                    "value": [{"value": coord} for coord in self.bbox]
                }
            }

        return {
            "city_ids": [str(self.city_id)],
            "search_data": {
                "form_data": {"data": form_data}
            },
        }


def parse_divar_url(url: str, use_bbox: bool = True) -> DivarSearchParams:
    """
    Parse a Divar web search URL and extract search parameters.

    Example URL:
    https://divar.ir/s/ahvaz/real-estate/golestan?bbox=48.6043%2C31.2658939%2C48.6834793%2C31.3184261&business-type=personal%2C
    """
    parsed = urlparse(url)
    path_parts = [p for p in parsed.path.split("/") if p]
    # Path pattern: /s/{city}/{category}/{neighborhood?}
    city_slug = "ahvaz"
    category_slug = "real-estate"
    neighborhood_slug = None

    if len(path_parts) >= 2 and path_parts[0] == "s":
        city_slug = path_parts[1]
    if len(path_parts) >= 3:
        category_slug = path_parts[2]
    if len(path_parts) >= 4:
        neighborhood_slug = path_parts[3]

    qs = parse_qs(parsed.query, keep_blank_values=True)

    # Extract business-type
    business_types = [
        bt.strip()
        for bt in ",".join(qs.get("business-type", [""])).split(",")
        if bt.strip()
    ]
    business_type = business_types[0] if business_types else "personal"

    # Extract bbox: lon_min, lat_min, lon_max, lat_max
    bbox = None
    bbox_raw = qs.get("bbox", [None])[0]
    if bbox_raw:
        try:
            coords = [float(x.strip()) for x in bbox_raw.split(",") if x.strip()]
            if len(coords) == 4:
                bbox = coords
        except (ValueError, TypeError):
            bbox = None

    return DivarSearchParams(
        city_slug=city_slug,
        category_slug=category_slug,
        neighborhood_slug=neighborhood_slug,
        business_type=business_type,
        bbox=bbox,
        use_bbox=use_bbox,
    )
