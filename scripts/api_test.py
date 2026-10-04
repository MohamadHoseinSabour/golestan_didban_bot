"""
Test the actual Divar search API endpoint directly.
Run: python scripts/api_test.py
"""
import asyncio
import json
from pathlib import Path

import httpx

OUTPUT = Path("docs")
FIXTURE = Path("tests/fixtures")

# Confirmed: Ahvaz city_id = 7 from v5 API
AHVAZ_CITY_ID = "7"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fa,en;q=0.9",
    "Content-Type": "application/json",
    "Origin": "https://divar.ir",
    "Referer": "https://divar.ir/s/ahvaz/real-estate/golestan?business-type=personal%2C",
    "x-standard-divar-error": "true",
    "x-divar-web-app-version": "the-wall-v14-133-9",
}


def make_search_payload(
    category: str = "real-estate",
    city_ids: list[str] = None,
    neighborhoods: list[str] = None,
    business_type: str = "personal",
    sort: str = "sort_date",
    page_size: int = 24,
    last_post_date: str = None,
    bbox: dict = None,
) -> dict:
    """Build the search API payload."""
    city_ids = city_ids or [AHVAZ_CITY_ID]

    form_data: dict = {
        "category": {"str": {"value": category}},
        "sort": {"str": {"value": sort}},
    }

    if business_type:
        form_data["business_type"] = {"str": {"value": business_type}}

    if neighborhoods:
        form_data["districts"] = {
            "str_array": {"value": neighborhoods}
        }

    payload: dict = {
        "city_ids": city_ids,
        "search_data": {
            "form_data": {"data": form_data},
        },
        "pagination_data": {
            "page_size": page_size,
        },
    }

    if last_post_date:
        payload["pagination_data"]["last_post_date"] = last_post_date

    if bbox:
        payload["map_state"] = {
            "camera_state": {
                "latitude": (bbox["lat_min"] + bbox["lat_max"]) / 2,
                "longitude": (bbox["lon_min"] + bbox["lon_max"]) / 2,
                "zoom": 14,
            }
        }

    return payload


async def run() -> None:
    OUTPUT.mkdir(exist_ok=True)
    FIXTURE.mkdir(parents=True, exist_ok=True)

    # Endpoints to try
    endpoints = [
        "https://api.divar.ir/v8/postlist/w/search",
        "https://api.divar.ir/v8/postlist/w/approximate-post-count",
    ]

    payload = make_search_payload(
        category="real-estate",
        city_ids=[AHVAZ_CITY_ID],
        neighborhoods=["golestan"],
        business_type="personal",
        sort="sort_date",
        page_size=24,
    )

    print("Search payload:")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print()

    async with httpx.AsyncClient(follow_redirects=True, timeout=20) as c:
        for endpoint in endpoints:
            print(f"\nTesting: {endpoint}")
            try:
                r = await c.post(endpoint, json=payload, headers=HEADERS)
                print(f"  Status: {r.status_code}")
                print(f"  Content-Type: {r.headers.get('content-type', 'unknown')}")

                if r.status_code == 200:
                    data = r.json()
                    print(f"  Response keys: {list(data.keys())}")

                    # Save fixture
                    fname = endpoint.split("/")[-1] + ".json"
                    # Sanitize
                    import re
                    text = json.dumps(data, ensure_ascii=False, indent=2)
                    text = re.sub(r"09\d{9}", "09XXXXXXXXX", text)
                    (FIXTURE / fname).write_text(text, encoding="utf-8")
                    print(f"  Saved to tests/fixtures/{fname}")

                    # Analyze structure
                    if "widget_list" in data:
                        wl = data["widget_list"]
                        print(f"  widget_list: {len(wl)} items")
                        if wl:
                            first = wl[0]
                            print(f"  First item type: {type(first)}")
                            if isinstance(first, dict):
                                print(f"  First item keys: {list(first.keys())}")
                                if "data" in first:
                                    print(f"  first.data keys: {list(first['data'].keys())}")

                    # Look for post tokens
                    text2 = json.dumps(data)
                    tokens = re.findall(r'"token"\s*:\s*"([A-Za-z0-9_-]{5,20})"', text2)
                    print(f"  Tokens found: {len(tokens)}")
                    if tokens:
                        print(f"  Sample tokens: {tokens[:3]}")

                        # Test detail for first token
                        token = tokens[0]
                        detail_url = f"https://api.divar.ir/v8/posts-v2/web/{token}"
                        print(f"\n  Testing detail for token={token}: {detail_url}")
                        dr = await c.get(detail_url, headers=HEADERS)
                        print(f"  Detail status: {dr.status_code}")
                        if dr.status_code == 200:
                            detail = dr.json()
                            print(f"  Detail keys: {list(detail.keys())}")
                            # Save
                            text3 = json.dumps(detail, ensure_ascii=False, indent=2)
                            text3 = re.sub(r"09\d{9}", "09XXXXXXXXX", text3)
                            (FIXTURE / "sample_detail.json").write_text(text3, encoding="utf-8")
                            print("  Saved detail fixture")
                else:
                    print(f"  Response: {r.text[:500]}")

            except Exception as e:
                print(f"  Error: {e}")

    # Also test with alternate neighborhood parameter names
    print("\n\n=== Testing neighborhood parameter variants ===")
    for param_name in ["neighborhoods", "districts", "neighborhood", "district"]:
        form_data = {
            "category": {"str": {"value": "real-estate"}},
            "sort": {"str": {"value": "sort_date"}},
            "business_type": {"str": {"value": "personal"}},
            param_name: {"str_array": {"value": ["golestan"]}},
        }
        payload2 = {
            "city_ids": [AHVAZ_CITY_ID],
            "search_data": {"form_data": {"data": form_data}},
            "pagination_data": {"page_size": 5},
        }
        async with httpx.AsyncClient(timeout=10) as c:
            try:
                r = await c.post(
                    "https://api.divar.ir/v8/postlist/w/search",
                    json=payload2, headers=HEADERS
                )
                import re
                token_count = len(re.findall(r'"token"', r.text))
                print(f"  param={param_name}: status={r.status_code}, tokens={token_count}")
            except Exception as e:
                print(f"  param={param_name}: error={e}")


if __name__ == "__main__":
    asyncio.run(run())
