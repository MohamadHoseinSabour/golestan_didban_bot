"""
Inspect the structure of list_widgets and test posts-v2/web/<token> for details.
"""
import asyncio
import json
import re
import sys
from pathlib import Path

import httpx

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

FIXTURE = Path("tests/fixtures")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fa,en;q=0.9",
    "x-web-serving-mode": "desktop",
}

def sanitize(data):
    text = json.dumps(data, ensure_ascii=False, indent=2)
    return re.sub(r"09\d{9}", "09XXXXXXXXX", text)

async def inspect():
    # 1. Read postlist_search.json
    data = json.loads((FIXTURE / "postlist_search.json").read_text(encoding="utf-8"))
    widgets = data.get("list_widgets", [])
    print(f"Total list_widgets: {len(widgets)}")

    first_post_widget = None
    tokens = []
    for w in widgets:
        widget_type = w.get("widget_type")
        widget_data = w.get("data", {})
        token = widget_data.get("token")
        if token and token not in tokens:
            tokens.append(token)
            if not first_post_widget:
                first_post_widget = w

    print(f"Unique tokens in list_widgets: {len(tokens)}")
    print(f"First widget type: {first_post_widget.get('widget_type') if first_post_widget else None}")
    print("\nFirst post widget data:")
    if first_post_widget:
        print(json.dumps(first_post_widget.get("data", {}), ensure_ascii=False, indent=2)[:1500])

    # Check pagination in search response
    pagination = data.get("pagination")
    print(f"\nPagination object: {json.dumps(pagination, ensure_ascii=False, indent=2)}")

    # 2. Test detail API for first 3 tokens
    async with httpx.AsyncClient(timeout=20) as client:
        for token in tokens[:3]:
            detail_url = f"https://api.divar.ir/v8/posts-v2/web/{token}"
            print(f"\n--- Testing Detail API: {detail_url} ---")
            r = await client.get(detail_url, headers=HEADERS)
            print(f"Status: {r.status_code}")
            if r.status_code == 200:
                detail_data = r.json()
                print("Detail keys:", list(detail_data.keys()))
                (FIXTURE / f"detail_{token}.json").write_text(sanitize(detail_data), encoding="utf-8")

                # Check widgets in detail
                sections = detail_data.get("sections", [])
                print(f"Detail sections count: {len(sections)}")
                for i, sec in enumerate(sections[:3]):
                    print(f"  Section {i} name/title: {sec.get('section_name')} - widgets: {len(sec.get('widgets', []))}")
                    for w in sec.get("widgets", [])[:5]:
                        wtype = w.get("widget_type")
                        wdata = w.get("data", {})
                        title = wdata.get("title") or wdata.get("value")
                        print(f"    Widget: {wtype} -> {title}")

                # Also check seo, web_info, etc.
                if "web_info" in detail_data:
                    print("web_info:", detail_data["web_info"])
            else:
                print(f"Error {r.status_code}: {r.text[:200]}")

if __name__ == "__main__":
    asyncio.run(inspect())
