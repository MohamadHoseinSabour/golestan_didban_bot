"""
Test postlist/w/search and mapview/viewport using the exact discovered protobuf JSON format.
"""
import asyncio
import json
import re
from pathlib import Path

import httpx

OUTPUT = Path("docs")
FIXTURE = Path("tests/fixtures")
OUTPUT.mkdir(exist_ok=True)
FIXTURE.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fa,en;q=0.9",
    "Content-Type": "application/json",
    "Origin": "https://divar.ir",
    "Referer": "https://divar.ir/s/ahvaz/real-estate/golestan?bbox=48.6043%2C31.2658939%2C48.6834793%2C31.3184261&business-type=personal%2C",
    "x-web-serving-mode": "desktop",
}

def sanitize(data):
    text = json.dumps(data, ensure_ascii=False, indent=2)
    return re.sub(r"09\d{9}", "09XXXXXXXXX", text)

async def test_search():
    async with httpx.AsyncClient(timeout=25) as client:
        # 1. Test mapview/viewport (we know from Playwright that this returned 200)
        viewport_payload = {
            "search_data": {
                "form_data": {
                    "data": {
                        "bbox": {
                            "repeated_float": {
                                "value": [
                                    {"value": 48.6043},
                                    {"value": 31.2658939},
                                    {"value": 48.6834793},
                                    {"value": 31.3184261}
                                ]
                            }
                        },
                        "business-type": {
                            "repeated_string": {
                                "value": ["personal"]
                            }
                        },
                        "map_free_roaming": {
                            "boolean": {
                                "value": True
                            }
                        },
                        "category": {
                            "str": {
                                "value": "real-estate"
                            }
                        },
                        "districts": {
                            "repeated_string": {
                                "value": ["323"]
                            }
                        }
                    }
                }
            },
            "camera_info": {
                "bbox": {
                    "min_latitude": 31.252807,
                    "min_longitude": 48.604301,
                    "max_latitude": 31.331504,
                    "max_longitude": 48.683479
                },
                "place_hash": "7|323|real-estate||",
                "zoom": 12.29
            },
            "city_ids": ["7"],
            "user_selected_location": {
                "places": [{"place_id": "7"}]
            }
        }

        print("\n--- Testing POST /v8/mapview/viewport ---")
        try:
            r = await client.post(
                "https://api.divar.ir/v8/mapview/viewport",
                json=viewport_payload,
                headers=HEADERS
            )
            print(f"Status: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                print("Viewport keys:", list(data.keys()))
                (FIXTURE / "mapview_viewport.json").write_text(sanitize(data), encoding="utf-8")
                # Look for posts or pins
                text = json.dumps(data)
                tokens = re.findall(r'"token"\s*:\s*"([A-Za-z0-9_-]+)"', text)
                print(f"Tokens in viewport: {len(tokens)}")
                if tokens:
                    print("Sample tokens:", tokens[:5])
            else:
                print("Error body:", r.text[:300])
        except Exception as e:
            print("Viewport error:", e)

        # 2. Test /v8/postlist/w/search WITHOUT pagination_data
        search_payload_no_pag = {
            "city_ids": ["7"],
            "search_data": {
                "form_data": {
                    "data": {
                        "category": {"str": {"value": "real-estate"}},
                        "business-type": {"repeated_string": {"value": ["personal"]}},
                        "districts": {"repeated_string": {"value": ["323"]}}
                    }
                }
            }
        }
        print("\n--- Testing POST /v8/postlist/w/search (no pagination_data) ---")
        try:
            r = await client.post(
                "https://api.divar.ir/v8/postlist/w/search",
                json=search_payload_no_pag,
                headers=HEADERS
            )
            print(f"Status: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                print("Search keys:", list(data.keys()))
                (FIXTURE / "postlist_search.json").write_text(sanitize(data), encoding="utf-8")
                tokens = re.findall(r'"token"\s*:\s*"([A-Za-z0-9_-]+)"', json.dumps(data))
                print(f"Tokens in search: {len(tokens)}")
                if tokens:
                    print("Sample tokens:", tokens[:5])
            else:
                print("Error body:", r.text[:300])
        except Exception as e:
            print("Search error:", e)

if __name__ == "__main__":
    asyncio.run(test_search())
