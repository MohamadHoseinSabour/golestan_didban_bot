"""
Divar reconnaissance script.
Run this to discover API endpoints, field mappings, and scraping strategy.
Results are written to docs/divar_recon.md and tests/fixtures/.

Usage:
    python scripts/recon.py [--proxy PROXY_URL] [--output-dir docs]
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DIVAR_URL = (
    "https://divar.ir/s/ahvaz/real-estate/golestan"
    "?bbox=48.6043%2C31.2658939%2C48.6834793%2C31.3184261"
    "&business-type=personal%2C"
    "&map_bbox=48.604302%2C31.265893%2C48.68348%2C31.318427"
    "&map_free_roaming=true"
    "&map_place_hash=7%7C%7Creal-estate%7C%7C"
)

API_LIST_URL = "https://api.divar.ir/v8/postlist/w/search"
API_DETAIL_BASE = "https://api.divar.ir/v8/posts-v2/web"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fa,en;q=0.9",
    "Referer": "https://divar.ir/",
    "Origin": "https://divar.ir",
    "x-standard-divar-error": "true",
    "content-type": "application/json",
}

OUTPUT_DIR = Path(__file__).parent.parent / "docs"
FIXTURE_DIR = Path(__file__).parent.parent / "tests" / "fixtures"


# ---------------------------------------------------------------------------
# URL parser
# ---------------------------------------------------------------------------
def parse_divar_url(url: str) -> dict[str, Any]:
    """Extract structured parameters from a Divar search URL."""
    parsed = urlparse(url)
    path_parts = [p for p in parsed.path.split("/") if p]
    qs = parse_qs(parsed.query, keep_blank_values=True)

    # path: /s/{city}/{category}/{neighborhood}
    city = path_parts[1] if len(path_parts) > 1 else None
    category = path_parts[2] if len(path_parts) > 2 else None
    neighborhood = path_parts[3] if len(path_parts) > 3 else None

    # bbox: lon_min,lat_min,lon_max,lat_max
    bbox_raw = qs.get("bbox", [None])[0]
    bbox = None
    if bbox_raw:
        try:
            lon_min, lat_min, lon_max, lat_max = map(float, bbox_raw.split(","))
            bbox = {
                "lon_min": lon_min,
                "lat_min": lat_min,
                "lon_max": lon_max,
                "lat_max": lat_max,
            }
        except ValueError:
            pass

    business_types = [
        bt.strip()
        for bt in ",".join(qs.get("business-type", [""])).split(",")
        if bt.strip()
    ]

    return {
        "city": city,
        "category": category,
        "neighborhood": neighborhood,
        "bbox": bbox,
        "business_types": business_types,
        "map_free_roaming": qs.get("map_free_roaming", [None])[0],
        "map_place_hash": qs.get("map_place_hash", [None])[0],
        "raw_qs": dict(qs),
    }


# ---------------------------------------------------------------------------
# API calls
# ---------------------------------------------------------------------------
async def fetch_listing_api(
    client: httpx.AsyncClient,
    city: str,
    category: str,
    neighborhood: str | None,
    business_type: str | None,
    bbox: dict[str, float] | None,
    last_post_date: str | None = None,
    page_size: int = 24,
) -> dict[str, Any]:
    """Call the Divar search API and return raw JSON."""
    # Build form_data filters
    filters: list[dict[str, Any]] = [
        {"identifier": "category", "value": {"str": {"value": category}}},
        {"identifier": "sort", "value": {"str": {"value": "sort_date"}}},
    ]
    if business_type:
        filters.append(
            {"identifier": "business_type", "value": {"str": {"value": business_type}}}
        )
    if neighborhood:
        filters.append(
            {"identifier": "neighborhoods", "value": {"str": {"value": neighborhood}}}
        )

    payload: dict[str, Any] = {
        "city_ids": [city],
        "pagination_data": {
            "@type": "type.googleapis.com/post.search.server.domain.SearchPaginationData",
            "page_size": page_size,
        },
        "search_data": {
            "form_data": {
                "data": {f["identifier"]: f["value"] for f in filters}
            }
        },
    }

    if bbox:
        payload["search_data"]["coordinates"] = {
            "longitude_min": bbox["lon_min"],
            "latitude_min": bbox["lat_min"],
            "longitude_max": bbox["lon_max"],
            "latitude_max": bbox["lat_max"],
        }

    if last_post_date:
        payload["pagination_data"] = {
            **payload["pagination_data"],
            "last_post_date": last_post_date,
        }

    resp = await client.post(API_LIST_URL, json=payload, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()  # type: ignore[no-any-return]


async def fetch_detail_api(
    client: httpx.AsyncClient, token: str
) -> dict[str, Any]:
    """Fetch full post detail by token."""
    url = f"{API_DETAIL_BASE}/{token}"
    resp = await client.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Field extraction helpers
# ---------------------------------------------------------------------------
def sanitize_for_fixture(data: dict[str, Any]) -> dict[str, Any]:
    """Remove phone numbers and contact info from fixture data."""
    text = json.dumps(data, ensure_ascii=False)
    # Remove phone numbers (Iranian formats)
    text = re.sub(r"09\d{9}", "09XXXXXXXXX", text)
    text = re.sub(r"\+989\d{9}", "+989XXXXXXXXX", text)
    text = re.sub(r"0\d{2,3}[-\s]?\d{7,8}", "0XX-XXXXXXXX", text)
    return json.loads(text)  # type: ignore[no-any-return]


def extract_post_summary(post: dict[str, Any]) -> dict[str, Any]:
    """Extract key fields from a listing post object."""
    return {
        "token": post.get("token"),
        "title": post.get("title"),
        "district": post.get("district"),
        "city": post.get("city"),
        "business_type": post.get("business_type"),
        "category": post.get("category", {}).get("str"),
        "created_at": post.get("created_at"),
        "price": post.get("price"),
        "image_count": len(post.get("images", [])),
    }


# ---------------------------------------------------------------------------
# Main recon routine
# ---------------------------------------------------------------------------
async def run_recon(proxy: str | None = None) -> None:
    print("=" * 60)
    print("Divar Recon Script")
    print("=" * 60)

    # Parse URL
    params = parse_divar_url(DIVAR_URL)
    print(f"\n[URL Analysis]\n{json.dumps(params, ensure_ascii=False, indent=2)}")

    # Setup HTTP client
    transport_kwargs: dict[str, Any] = {}
    if proxy:
        transport_kwargs["proxy"] = proxy

    recon_results: dict[str, Any] = {
        "url_params": params,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "connectivity": {},
        "api_test": {},
        "field_map": {},
        "findings": [],
    }

    async with httpx.AsyncClient(**transport_kwargs, follow_redirects=True) as client:
        # ---------------------------------------------------------------
        # 1. Connectivity test
        # ---------------------------------------------------------------
        print("\n[1] Connectivity test...")
        for host, url in [
            ("divar.ir", "https://divar.ir"),
            ("api.divar.ir", "https://api.divar.ir"),
        ]:
            try:
                t0 = time.time()
                r = await client.get(url, headers=HEADERS, timeout=10)
                elapsed = time.time() - t0
                result = {
                    "status": r.status_code,
                    "latency_ms": round(elapsed * 1000),
                    "ok": r.status_code < 400,
                }
                print(f"  {host}: HTTP {r.status_code} ({elapsed*1000:.0f}ms)")
            except Exception as e:
                result = {"status": None, "error": str(e), "ok": False}
                print(f"  {host}: ERROR — {e}")
            recon_results["connectivity"][host] = result

        if not recon_results["connectivity"].get("api.divar.ir", {}).get("ok"):
            print("\n⛔ Cannot reach api.divar.ir. Stopping recon.")
            print("Possible causes: geo-block, network filter, or captcha.")
            print("Solutions: run on Iranian network, or use DIVAR_PROXY_URL.")
            _save_recon(recon_results, partial=True)
            return

        # ---------------------------------------------------------------
        # 2. API listing test — WITH business-type=personal filter
        # ---------------------------------------------------------------
        print("\n[2] API listing test (with personal filter)...")
        try:
            data_personal = await fetch_listing_api(
                client,
                city=params["city"] or "ahvaz",
                category=params["category"] or "real-estate",
                neighborhood=params["neighborhood"],
                business_type="personal",
                bbox=params["bbox"],
            )
            posts_personal = data_personal.get("list_widgets", []) or data_personal.get("widget_list", [])
            print(f"  With filter: {len(posts_personal)} items in response")
            recon_results["api_test"]["with_filter_count"] = len(posts_personal)
            recon_results["api_test"]["with_filter_keys"] = list(data_personal.keys())

            # Save raw response keys for analysis
            if posts_personal:
                first = posts_personal[0]
                recon_results["api_test"]["post_keys"] = list(first.keys()) if isinstance(first, dict) else type(first).__name__

        except httpx.HTTPStatusError as e:
            print(f"  HTTP error: {e.response.status_code} — {e.response.text[:200]}")
            recon_results["api_test"]["error"] = str(e)
        except Exception as e:
            print(f"  Error: {e}")
            recon_results["api_test"]["error"] = str(e)

        # ---------------------------------------------------------------
        # 3. API listing test — WITHOUT filter
        # ---------------------------------------------------------------
        print("\n[3] API listing test (without filter, for comparison)...")
        try:
            data_all = await fetch_listing_api(
                client,
                city=params["city"] or "ahvaz",
                category=params["category"] or "real-estate",
                neighborhood=params["neighborhood"],
                business_type=None,
                bbox=None,  # No bbox to get broader results
            )
            posts_all = data_all.get("list_widgets", []) or data_all.get("widget_list", [])
            print(f"  Without filter: {len(posts_all)} items")
            recon_results["api_test"]["without_filter_count"] = len(posts_all)
            recon_results["api_test"]["response_structure_all"] = list(data_all.keys())

        except Exception as e:
            print(f"  Error: {e}")

        # ---------------------------------------------------------------
        # 4. Fetch detail for first token
        # ---------------------------------------------------------------
        print("\n[4] Detail API test...")
        # Try to get tokens from whichever response worked
        sample_token = None
        for resp_data in [
            data_personal if "data_personal" in dir() else {},
            data_all if "data_all" in dir() else {},
        ]:
            widgets = resp_data.get("list_widgets", []) or resp_data.get("widget_list", [])
            for w in widgets:
                if isinstance(w, dict):
                    tok = (
                        w.get("token")
                        or (w.get("data", {}) or {}).get("token")
                        or (w.get("widget_type") == "POST_ROW" and w.get("data", {}).get("token"))
                    )
                    if tok:
                        sample_token = tok
                        break
            if sample_token:
                break

        if sample_token:
            print(f"  Testing detail for token: {sample_token}")
            try:
                detail = await fetch_detail_api(client, sample_token)
                recon_results["field_map"]["detail_top_keys"] = list(detail.keys())
                recon_results["findings"].append(f"Detail API works for token {sample_token}")

                # Save sanitized fixture
                FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
                sanitized = sanitize_for_fixture(detail)
                fixture_path = FIXTURE_DIR / "sample_detail.json"
                fixture_path.write_text(
                    json.dumps(sanitized, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                print(f"  Detail keys: {list(detail.keys())}")
                print(f"  Fixture saved: {fixture_path}")
            except Exception as e:
                print(f"  Detail error: {e}")
                recon_results["findings"].append(f"Detail API error: {e}")
        else:
            print("  No token found in listing response — check API structure")
            recon_results["findings"].append("Could not extract token from listing response")

        # ---------------------------------------------------------------
        # 5. Save listing fixtures
        # ---------------------------------------------------------------
        try:
            if "data_personal" in dir() and data_personal:
                san = sanitize_for_fixture(data_personal)
                (FIXTURE_DIR / "sample_listing_personal.json").write_text(
                    json.dumps(san, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            if "data_all" in dir() and data_all:
                san = sanitize_for_fixture(data_all)
                (FIXTURE_DIR / "sample_listing_all.json").write_text(
                    json.dumps(san, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            print("\n  Fixtures saved to tests/fixtures/")
        except Exception as e:
            print(f"  Fixture save error: {e}")

    _save_recon(recon_results, partial=False)
    print("\n✅ Recon complete. See docs/divar_recon.md")


def _save_recon(results: dict[str, Any], partial: bool = False) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Save raw JSON
    (OUTPUT_DIR / "divar_recon_raw.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # Save markdown summary
    md_path = OUTPUT_DIR / "divar_recon.md"
    md = f"""# Divar Recon Report
{'⚠️ PARTIAL — connectivity failed' if partial else '✅ Complete'}

**Date:** {results.get('timestamp', 'unknown')}

## URL Parameters
```json
{json.dumps(results.get('url_params', {}), ensure_ascii=False, indent=2)}
```

## Connectivity
| Host | Status | Latency |
|------|--------|---------|
"""
    for host, info in results.get("connectivity", {}).items():
        status = info.get("status", "ERROR")
        latency = f"{info.get('latency_ms', '?')}ms" if info.get("ok") else info.get("error", "?")
        md += f"| {host} | {status} | {latency} |\n"

    md += f"""
## API Test Results
```json
{json.dumps(results.get('api_test', {}), ensure_ascii=False, indent=2)}
```

## Field Map
```json
{json.dumps(results.get('field_map', {}), ensure_ascii=False, indent=2)}
```

## Findings
"""
    for f in results.get("findings", []):
        md += f"- {f}\n"

    md_path.write_text(md, encoding="utf-8")


if __name__ == "__main__":
    proxy = None
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--proxy" and i + 1 < len(sys.argv[1:]):
            proxy = sys.argv[i + 2]

    asyncio.run(run_recon(proxy=proxy))
