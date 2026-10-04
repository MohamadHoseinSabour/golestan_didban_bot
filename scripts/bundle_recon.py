"""
Search Divar JS bundles for API endpoint patterns.
Run: python scripts/bundle_recon.py
"""
import asyncio
import re
from pathlib import Path

import httpx

BUNDLE_URLS = [
    "https://s100.divarcdn.com/web-assets/2026/09/services-671.9c703b60.desktop.js",
    "https://s100.divarcdn.com/web-assets/2026/09/main.148f52e3.desktop.js",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://divar.ir/",
}

OUTPUT = Path("docs")


async def run() -> None:
    OUTPUT.mkdir(exist_ok=True)
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as c:
        for url in BUNDLE_URLS:
            name = url.split("/")[-1]
            print(f"\nFetching {name}...")
            try:
                r = await c.get(url, headers=HEADERS)
                print(f"  Status: {r.status_code}, Size: {len(r.text)}")
                text = r.text

                # Find all api.divar.ir paths
                api_paths = re.findall(
                    r'["\`]((?:https://api\.divar\.ir)?/v\d+/[/\w\-\{\}.]+)["\`]',
                    text
                )
                unique_paths = sorted(set(api_paths))
                if unique_paths:
                    print(f"  API paths ({len(unique_paths)}):")
                    for p in unique_paths[:40]:
                        print(f"    {p}")
                    out = OUTPUT / f"api_paths_{name}.txt"
                    out.write_text("\n".join(unique_paths), encoding="utf-8")
                    print(f"  Saved to {out}")

                # Look for search/postlist patterns
                patterns = [
                    (r'postlist', "postlist"),
                    (r'post-list', "post-list"),
                    (r'search', "search"),
                    (r'city_id', "city_id"),
                    (r'business.?type', "business_type"),
                    (r'form_data', "form_data"),
                    (r'widget_list', "widget_list"),
                    (r'list_widgets', "list_widgets"),
                ]
                print("  Key patterns:")
                for pattern, label in patterns:
                    matches = re.findall(
                        rf'.{{0,80}}{pattern}.{{0,80}}', text
                    )
                    if matches:
                        print(f"    [{label}] {matches[0][:120]}")

            except Exception as e:
                print(f"  Error: {e}")


if __name__ == "__main__":
    asyncio.run(run())
