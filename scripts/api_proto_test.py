"""
Test Divar API with correct protobuf @type annotations.
Run: python scripts/api_proto_test.py
"""
import asyncio
import json
import re
from pathlib import Path

import httpx

OUTPUT = Path("docs")
FIXTURE = Path("tests/fixtures")
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


def make_payload_v1() -> dict:
    """Payload with @type for pagination (protobuf JSON format)."""
    return {
        "city_ids": [AHVAZ_CITY_ID],
        "search_data": {
            "form_data": {
                "data": {
                    "category": {"str": {"value": "real-estate"}},
                    "sort": {"str": {"value": "sort_date"}},
                    "business_type": {"str": {"value": "personal"}},
                }
            }
        },
        "pagination_data": {
            "@type": "type.googleapis.com/post.search.server.domain.SearchPaginationData",
            "page_size": 24,
        },
    }


def make_payload_v2() -> dict:
    """Payload with districts filter."""
    return {
        "city_ids": [AHVAZ_CITY_ID],
        "search_data": {
            "form_data": {
                "data": {
                    "category": {"str": {"value": "real-estate"}},
                    "sort": {"str": {"value": "sort_date"}},
                    "business_type": {"str": {"value": "personal"}},
                    "districts": {"str_array": {"value": ["golestan"]}},
                }
            }
        },
        "pagination_data": {
            "@type": "type.googleapis.com/post.search.server.domain.SearchPaginationData",
            "page_size": 24,
        },
    }


def make_payload_v3_with_bbox() -> dict:
    """Payload with bbox map state."""
    return {
        "city_ids": [AHVAZ_CITY_ID],
        "search_data": {
            "form_data": {
                "data": {
                    "category": {"str": {"value": "real-estate"}},
                    "sort": {"str": {"value": "sort_date"}},
                    "business_type": {"str": {"value": "personal"}},
                    "districts": {"str_array": {"value": ["golestan"]}},
                }
            }
        },
        "pagination_data": {
            "@type": "type.googleapis.com/post.search.server.domain.SearchPaginationData",
            "page_size": 24,
        },
        # bbox: 48.6043,31.2658939,48.6834793,31.3184261
        "map_state": {
            "@type": "type.googleapis.com/location.MapState",
            "camera_state": {
                "latitude": (31.2658939 + 31.3184261) / 2,
                "longitude": (48.6043 + 48.6834793) / 2,
            },
            "bounding_box": {
                "min_lat": 31.2658939,
                "min_lon": 48.6043,
                "max_lat": 31.3184261,
                "max_lon": 48.6834793,
            }
        }
    }


async def try_payload(client: httpx.AsyncClient, label: str, payload: dict) -> dict | None:
    """Try a payload and return parsed response if successful."""
    print(f"\n[{label}]")
    print(f"  Payload keys: {list(payload.keys())}")
    try:
        r = await client.post(
            "https://api.divar.ir/v8/postlist/w/search",
            json=payload, headers=HEADERS, timeout=20
        )
        print(f"  Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"  Response keys: {list(data.keys())}")
            # Count tokens
            token_count = len(re.findall(r'"token"', r.text))
            print(f"  Token count: {token_count}")
            if "widget_list" in data:
                print(f"  widget_list length: {len(data['widget_list'])}")
                if data["widget_list"]:
                    first = data["widget_list"][0]
                    if isinstance(first, dict):
                        print(f"  First widget keys: {list(first.keys())}")
            return data
        else:
            print(f"  Error: {r.text[:300]}")
    except Exception as e:
        print(f"  Exception: {e}")
    return None


def sanitize(data) -> str:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    return re.sub(r"09\d{9}", "09XXXXXXXXX", text)


async def run() -> None:
    OUTPUT.mkdir(exist_ok=True)
    FIXTURE.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(follow_redirects=True, timeout=20) as c:
        # Try different payload variants
        payloads = [
            ("v1_basic_with_type", make_payload_v1()),
            ("v2_with_district", make_payload_v2()),
            ("v3_with_bbox", make_payload_v3_with_bbox()),
        ]

        for label, payload in payloads:
            result = await try_payload(c, label, payload)
            if result:
                (FIXTURE / f"listing_{label}.json").write_text(
                    sanitize(result), encoding="utf-8"
                )
                print(f"  Saved fixture: listing_{label}.json")

                # Get first token and test detail
                tokens = re.findall(r'"token"\s*:\s*"([A-Za-z0-9_-]{5,25})"', json.dumps(result))
                if tokens:
                    print(f"\n  Testing detail API for token: {tokens[0]}")
                    dr = await c.get(
                        f"https://api.divar.ir/v8/posts-v2/web/{tokens[0]}",
                        headers=HEADERS, timeout=15
                    )
                    print(f"  Detail status: {dr.status_code}")
                    if dr.status_code == 200:
                        detail = dr.json()
                        print(f"  Detail keys: {list(detail.keys())}")
                        (FIXTURE / "sample_detail.json").write_text(
                            sanitize(detail), encoding="utf-8"
                        )
                        print("  Saved detail fixture!")
                break  # Stop after first success

        # Also test alternate sort values
        print("\n\n=== Sort value tests ===")
        for sort_val in ["sort_date", "sort_price_ascending", "sort_price_descending"]:
            p = make_payload_v1()
            p["search_data"]["form_data"]["data"]["sort"] = {"str": {"value": sort_val}}
            p["pagination_data"]["page_size"] = 5
            r = await c.post(
                "https://api.divar.ir/v8/postlist/w/search",
                json=p, headers=HEADERS, timeout=10
            )
            token_count = len(re.findall(r'"token"', r.text))
            print(f"  sort={sort_val}: status={r.status_code}, tokens={token_count}")


if __name__ == "__main__":
    asyncio.run(run())
