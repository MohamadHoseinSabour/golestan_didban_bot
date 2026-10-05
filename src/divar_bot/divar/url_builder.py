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
    ("7", "kuy-saadi"): "4574",
    ("7", "saadi"): "4574",
}

# Mapping human-facing web URL slugs to internal Divar Protobuf category slugs
CATEGORY_SLUG_MAP: dict[str, str] = {
    # Rent
    "rent-residential": "residential-rent",
    "rent-apartment": "apartment-rent",
    "rent-villa": "house-villa-rent",
    "rent-commercial": "commercial-rent",
    "rent-room": "suite-apartment-rent",
    # Buy / Sell
    "buy-apartment": "apartment-sell",
    "buy-residential": "residential-sell",
    "buy-villa": "house-villa-sell",
    "buy-commercial": "commercial-sell",
    "buy-old-house": "house-villa-sell",
    # Direct / API category values (pass-through)
    "residential-rent": "residential-rent",
    "apartment-rent": "apartment-rent",
    "house-villa-rent": "house-villa-rent",
    "commercial-rent": "commercial-rent",
    "apartment-sell": "apartment-sell",
    "residential-sell": "residential-sell",
    "house-villa-sell": "house-villa-sell",
    "commercial-sell": "commercial-sell",
    "real-estate": "real-estate",
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
        districts: list[str] | None = None,
        business_type: str | None = "personal",
        bbox: list[float] | None = None,
        use_bbox: bool = True,
    ) -> None:
        self.city_slug = city_slug
        self.category_slug = category_slug
        self.neighborhood_slug = neighborhood_slug
        self.city_id = city_id or WELL_KNOWN_CITIES.get(city_slug, "7")

        all_districts: list[str] = []
        if districts:
            all_districts.extend(str(d) for d in districts if str(d).strip())
        if district_id and str(district_id) not in all_districts:
            all_districts.append(str(district_id))

        well_known = WELL_KNOWN_DISTRICTS.get((self.city_id, neighborhood_slug or ""))
        if well_known and well_known not in all_districts:
            all_districts.insert(0, well_known)

        self.districts = list(dict.fromkeys(all_districts))
        self.district_id = self.districts[0] if self.districts else None
        self.business_type = business_type
        self.bbox = bbox
        self.use_bbox = use_bbox

    def to_api_payload(self, page_size: int = 24) -> dict[str, Any]:
        """Generate the exact protobuf-over-JSON payload for api.divar.ir search."""
        api_category = CATEGORY_SLUG_MAP.get(
            self.category_slug, self.category_slug or "real-estate"
        )
        form_data: dict[str, Any] = {
            "category": {"str": {"value": api_category}},
        }

        if self.business_type:
            form_data["business-type"] = {
                "repeated_string": {"value": [self.business_type]}
            }

        if self.districts:
            form_data["districts"] = {
                "repeated_string": {"value": [str(d) for d in self.districts]}
            }
        elif self.district_id:
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

    city_id = WELL_KNOWN_CITIES.get(city_slug, "7")
    districts: list[str] = []

    # 1. From neighborhood slug
    if neighborhood_slug:
        n_dist = WELL_KNOWN_DISTRICTS.get((city_id, neighborhood_slug))
        if n_dist:
            districts.append(n_dist)

    # 2. From 'districts' query parameter (e.g. &districts=4574,)
    for d_raw in qs.get("districts", []):
        for token in d_raw.split(","):
            token = token.strip()
            if token.isdigit() and token not in districts:
                districts.append(token)

    # 3. From 'map_place_hash' (e.g. 7|323,4574|residential-rent||)
    for mph in qs.get("map_place_hash", []):
        parts = mph.split("|")
        if len(parts) >= 2 and parts[1]:
            for token in parts[1].split(","):
                token = token.strip()
                if token.isdigit() and token not in districts:
                    districts.append(token)

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
        city_id=city_id,
        districts=districts,
        business_type=business_type,
        bbox=bbox,
        use_bbox=use_bbox,
    )
