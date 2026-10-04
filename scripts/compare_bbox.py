"""
Test whether bbox actually filters listings differently than district-only.
"""
import asyncio
import sys

import httpx

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fa,en;q=0.9",
    "x-web-serving-mode": "desktop",
    "Content-Type": "application/json",
}

async def run_comparison():
    async with httpx.AsyncClient(timeout=20) as client:
        # 1. District only
        p_district_only = {
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
        r1 = await client.post("https://api.divar.ir/v8/postlist/w/search", json=p_district_only, headers=HEADERS)
        data1 = r1.json() if r1.status_code == 200 else {}
        tokens1 = [
            w.get("data", {}).get("token")
            for w in data1.get("list_widgets", [])
            if w.get("data", {}).get("token")
        ]
        print(f"District only: Status {r1.status_code}, {len(tokens1)} tokens")

        # 2. District + bbox in form_data
        p_with_bbox = {
            "city_ids": ["7"],
            "search_data": {
                "form_data": {
                    "data": {
                        "category": {"str": {"value": "real-estate"}},
                        "business-type": {"repeated_string": {"value": ["personal"]}},
                        "districts": {"repeated_string": {"value": ["323"]}},
                        "bbox": {
                            "repeated_float": {
                                "value": [
                                    {"value": 48.6043},
                                    {"value": 31.2658939},
                                    {"value": 48.6834793},
                                    {"value": 31.3184261}
                                ]
                            }
                        }
                    }
                }
            }
        }
        r2 = await client.post("https://api.divar.ir/v8/postlist/w/search", json=p_with_bbox, headers=HEADERS)
        data2 = r2.json() if r2.status_code == 200 else {}
        tokens2 = [
            w.get("data", {}).get("token")
            for w in data2.get("list_widgets", [])
            if w.get("data", {}).get("token")
        ]
        print(f"District + bbox: Status {r2.status_code}, {len(tokens2)} tokens")

        diff = set(tokens1).symmetric_difference(set(tokens2))
        print(f"Difference in tokens: {len(diff)}")
        if diff:
            print("Diff tokens:", list(diff)[:5])
        else:
            print("Both returned identical set of tokens on page 1!")

if __name__ == "__main__":
    asyncio.run(run_comparison())
