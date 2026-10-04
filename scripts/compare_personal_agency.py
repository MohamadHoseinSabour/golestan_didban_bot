"""
Compare personal vs agency listings on Divar:
1. Fetch 30+ listings with business-type: personal
2. Fetch 30+ listings without business-type filter (all)
3. Check business_type and business_ref in details
4. Measure filter accuracy and agency leakage
"""
import asyncio
import json
import sys
from pathlib import Path

import httpx

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

FIXTURE = Path("tests/fixtures")
DOCS = Path("docs")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fa,en;q=0.9",
    "x-web-serving-mode": "desktop",
    "Content-Type": "application/json",
}

def sanitize(data):
    import re
    return re.sub(r"09\d{9}", "09XXXXXXXXX", json.dumps(data, ensure_ascii=False, indent=2))

async def fetch_listings(client, filter_personal: bool):
    form_data = {
        "category": {"str": {"value": "real-estate"}},
        "districts": {"repeated_string": {"value": ["323"]}},
    }
    if filter_personal:
        form_data["business-type"] = {"repeated_string": {"value": ["personal"]}}

    payload = {
        "city_ids": ["7"],
        "search_data": {
            "form_data": {"data": form_data}
        }
    }

    r = await client.post("https://api.divar.ir/v8/postlist/w/search", json=payload, headers=HEADERS)
    r.raise_for_status()
    data = r.json()
    tokens = [
        w.get("data", {}).get("token")
        for w in data.get("list_widgets", [])
        if w.get("data", {}).get("token")
    ]
    return tokens, data

async def fetch_details(client, tokens):
    details = []
    for tok in tokens:
        try:
            r = await client.get(f"https://api.divar.ir/v8/posts-v2/web/{tok}", headers=HEADERS)
            if r.status_code == 200:
                details.append(r.json())
            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"Error fetching {tok}: {e}")
    return details

async def main():
    async with httpx.AsyncClient(timeout=25) as client:
        print("Fetching with personal filter...")
        personal_tokens, personal_raw = await fetch_listings(client, filter_personal=True)
        print(f"Found {len(personal_tokens)} personal tokens")
        (FIXTURE / "sample_listing_personal.json").write_text(sanitize(personal_raw), encoding="utf-8")

        print("Fetching without filter (all)...")
        all_tokens, all_raw = await fetch_listings(client, filter_personal=False)
        print(f"Found {len(all_tokens)} all tokens")
        (FIXTURE / "sample_listing_all.json").write_text(sanitize(all_raw), encoding="utf-8")

        # Fetch details for 10 from each to inspect business types
        print("Fetching details for personal sample...")
        personal_details = await fetch_details(client, personal_tokens[:10])

        print("Fetching details for all sample...")
        all_details = await fetch_details(client, all_tokens[:10])

        # Analyze
        print("\n--- Personal filter details analysis ---")
        personal_business_types = {}
        for d in personal_details:
            w_eng = d.get("webengage", {})
            b_type = w_eng.get("business_type")
            b_ref = w_eng.get("business_ref")
            personal_business_types[b_type] = personal_business_types.get(b_type, 0) + 1
            print(f"Token: {w_eng.get('token')} | Type: {b_type} | Ref: '{b_ref}' | Title: {d.get('seo', {}).get('title')[:40]}")

        print("\n--- All (unfiltered) details analysis ---")
        all_business_types = {}
        for d in all_details:
            w_eng = d.get("webengage", {})
            b_type = w_eng.get("business_type")
            b_ref = w_eng.get("business_ref")
            all_business_types[b_type] = all_business_types.get(b_type, 0) + 1
            print(f"Token: {w_eng.get('token')} | Type: {b_type} | Ref: '{b_ref}' | Title: {d.get('seo', {}).get('title')[:40]}")

        print("\nSummary of personal filter:", personal_business_types)
        print("Summary of unfiltered:", all_business_types)

if __name__ == "__main__":
    asyncio.run(main())
