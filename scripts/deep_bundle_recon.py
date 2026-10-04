"""
Deep analysis of Divar services bundle to find exact API endpoints and request format.
Run: python scripts/deep_bundle_recon.py
"""
import asyncio
import re
from pathlib import Path

import httpx

SERVICES_URL = "https://s100.divarcdn.com/web-assets/2026/09/services-671.9c703b60.desktop.js"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://divar.ir/",
}
OUTPUT = Path("docs")


async def run() -> None:
    OUTPUT.mkdir(exist_ok=True)
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as c:
        r = await c.get(SERVICES_URL, headers=HEADERS)
        text = r.text
        print(f"Bundle size: {len(text)} chars")

        # Save full bundle for offline analysis
        (OUTPUT / "services_bundle.js").write_text(text, encoding="utf-8")
        print("Saved to docs/services_bundle.js")

        # Find all string literals containing API paths
        print("\n=== API path strings ===")
        path_strings = re.findall(r'"(/v\d[^"]{0,100})"', text)
        unique_paths = sorted(set(path_strings))
        for p in unique_paths:
            print(f"  {p}")
        (OUTPUT / "api_paths.txt").write_text("\n".join(unique_paths), encoding="utf-8")

        # Find postlist endpoint context
        print("\n=== postlist context ===")
        matches = re.finditer(r'.{0,200}postlist.{0,200}', text)
        for m in matches:
            snippet = m.group(0)
            if "w/search" in snippet or "approximate" in snippet or "post(" in snippet.lower():
                print(f"  {snippet[:300]}")
                print("  ---")

        # Find search payload structure
        print("\n=== search payload structure ===")
        payload_matches = re.finditer(r'.{0,100}form_data.{0,300}', text)
        for i, m in enumerate(payload_matches):
            if i > 3:
                break
            print(f"  {m.group(0)[:300]}")
            print("  ---")

        # Find city_ids usage
        print("\n=== city_ids context ===")
        city_matches = re.finditer(r'.{0,100}city_ids.{0,200}', text)
        for i, m in enumerate(city_matches):
            if i > 5:
                break
            print(f"  {m.group(0)[:250]}")
            print("  ---")

        # Find business_type filter context
        print("\n=== business_type context ===")
        bt_matches = re.finditer(r'.{0,100}business.type.{0,200}', text)
        for i, m in enumerate(bt_matches):
            if i > 5:
                break
            snippet = m.group(0)
            if "filter" in snippet.lower() or "search" in snippet.lower() or "form" in snippet.lower():
                print(f"  {snippet[:250]}")
                print("  ---")

        # Find the rF constant (API base URL)
        print("\n=== rF / API base URL ===")
        rf_matches = re.finditer(r'rF\s*[=:]\s*["\`]([^"` ]{5,100})["\`]', text)
        for m in rf_matches:
            print(f"  rF = {m.group(1)}")

        # Also look for API_URL constant
        api_url_matches = re.finditer(r'API_URL[^"]{0,20}"([^"]{5,100})"', text)
        for m in api_url_matches:
            print(f"  API_URL = {m.group(1)}")

        # Find pagination/cursor structure
        print("\n=== pagination context ===")
        pag_matches = re.finditer(r'.{0,50}pagination.{0,200}', text)
        for i, m in enumerate(pag_matches):
            if i > 3:
                break
            snippet = m.group(0)
            if "last_post" in snippet or "page" in snippet or "cursor" in snippet:
                print(f"  {snippet[:250]}")
                print("  ---")

        # Find sort options
        print("\n=== sort options ===")
        sort_matches = re.finditer(r'.{0,50}sort.{0,100}', text)
        for i, m in enumerate(sort_matches):
            snippet = m.group(0)
            if "sort_date" in snippet or "sort_price" in snippet:
                print(f"  {snippet[:150]}")
                print("  ---")
                if i > 5:
                    break


if __name__ == "__main__":
    asyncio.run(run())
