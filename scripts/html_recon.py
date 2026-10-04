"""
Deep HTML recon of Divar search page.
Extracts embedded JSON, discovers API endpoints from XHR calls.
Run: python scripts/html_recon.py
"""
import asyncio
import json
import re
from pathlib import Path

import httpx

DIVAR_URL = (
    "https://divar.ir/s/ahvaz/real-estate/golestan"
    "?bbox=48.6043%2C31.2658939%2C48.6834793%2C31.3184261"
    "&business-type=personal%2C"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fa,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
}

OUTPUT_DIR = Path("docs")
FIXTURE_DIR = Path("tests/fixtures")


def extract_next_data(html: str) -> dict | None:
    """Extract __NEXT_DATA__ JSON from Next.js page."""
    pattern = r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>'
    m = re.search(pattern, html, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    return None


def find_api_references(html: str) -> list[str]:
    """Find API endpoint references in JavaScript bundles."""
    # Look for api.divar.ir URLs
    api_refs = re.findall(r'https?://api\.divar\.ir[/\w\-\.%?=&]*', html)
    # Also look for relative API paths
    path_refs = re.findall(r'["\'](/v\d+/[/\w\-]+)["\']', html)
    return list(set(api_refs + path_refs))


def extract_posts_from_html(html: str) -> list[dict]:
    """Try to extract post data from embedded JSON in HTML."""
    posts = []

    # Try __NEXT_DATA__
    nd = extract_next_data(html)
    if nd:
        # Navigate the Next.js data structure
        # Common path: pageProps -> initialState -> postList -> widgetList
        def find_lists(obj, depth=0):
            if depth > 8:
                return
            if isinstance(obj, dict):
                # Look for widget_list or list_widgets
                for key in ("widget_list", "list_widgets", "posts", "items", "data"):
                    if key in obj and isinstance(obj[key], list) and len(obj[key]) > 0:
                        first = obj[key][0]
                        if isinstance(first, dict) and ("token" in first or "data" in first):
                            posts.extend(obj[key])
                for v in obj.values():
                    find_lists(v, depth + 1)
            elif isinstance(obj, list):
                for item in obj[:5]:
                    find_lists(item, depth + 1)

        find_lists(nd)

    return posts


def sanitize(data) -> str:
    """Remove phone numbers from JSON string."""
    text = json.dumps(data, ensure_ascii=False, indent=2)
    text = re.sub(r"09\d{9}", "09XXXXXXXXX", text)
    text = re.sub(r"\+989\d{9}", "+989XXXXXXXXX", text)
    return text


async def run() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    print("=== Divar HTML Recon ===\n")

    async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
        # 1. Fetch main search page
        print(f"Fetching: {DIVAR_URL}")
        r = await client.get(DIVAR_URL, headers=HEADERS)
        print(f"Status: {r.status_code}, Size: {len(r.text)} bytes")

        html = r.text

        # 2. Check for Next.js data
        nd = extract_next_data(html)
        if nd:
            print("\n[+] Found __NEXT_DATA__")
            nd_path = OUTPUT_DIR / "divar_nextdata.json"
            nd_path.write_text(sanitize(nd), encoding="utf-8")
            print(f"    Saved to {nd_path}")

            # Show top-level structure
            def show_structure(obj, prefix="", depth=0):
                if depth > 4:
                    return
                if isinstance(obj, dict):
                    for k, v in list(obj.items())[:15]:
                        vtype = type(v).__name__
                        vlen = f"[{len(v)}]" if isinstance(v, (dict, list)) else ""
                        print(f"  {prefix}{k}: {vtype}{vlen}")
                        if isinstance(v, dict) and depth < 2:
                            show_structure(v, prefix + "  ", depth + 1)

            show_structure(nd)
        else:
            print("\n[-] No __NEXT_DATA__ found")

        # 3. Find API references
        api_refs = find_api_references(html)
        if api_refs:
            print(f"\n[+] API references found ({len(api_refs)}):")
            for ref in sorted(set(api_refs))[:20]:
                print(f"  {ref}")

        # 4. Extract posts from HTML
        posts = extract_posts_from_html(html)
        if posts:
            print(f"\n[+] Found {len(posts)} posts in HTML")
            print(f"    First post keys: {list(posts[0].keys()) if isinstance(posts[0], dict) else type(posts[0])}")
            # Save fixture
            fixture = FIXTURE_DIR / "html_posts.json"
            fixture.write_text(sanitize(posts[:5]), encoding="utf-8")
            print(f"    Saved 5 posts to {fixture}")
        else:
            print("\n[-] No posts found in HTML — likely dynamic rendering needed")

        # 5. Check script tags for bundle URLs
        bundle_urls = re.findall(r'src="(/_next/static/chunks/[^"]+\.js)"', html)
        print(f"\n[+] JS bundles: {len(bundle_urls)} found")

        # 6. Try to find API endpoint in bundles (first one)
        if bundle_urls:
            bundle_url = "https://divar.ir" + bundle_urls[0]
            print(f"    Checking bundle: {bundle_url}")
            try:
                br = await client.get(bundle_url, headers={
                    "User-Agent": HEADERS["User-Agent"],
                    "Referer": "https://divar.ir/",
                })
                bundle_text = br.text
                # Find API endpoint patterns
                api_patterns = re.findall(
                    r'["\`](https://api\.divar\.ir/v\d+/[/\w\-\{\}]+)["\`]', bundle_text
                )
                if api_patterns:
                    print(f"    API endpoints in bundle ({len(api_patterns)}):")
                    for ep in sorted(set(api_patterns))[:15]:
                        print(f"      {ep}")
                    # Save for analysis
                    (OUTPUT_DIR / "bundle_api_endpoints.txt").write_text(
                        "\n".join(sorted(set(api_patterns))), encoding="utf-8"
                    )
            except Exception as e:
                print(f"    Bundle fetch error: {e}")

        # 7. Save raw HTML fragment (first 100KB)
        (OUTPUT_DIR / "divar_page_head.html").write_text(
            html[:100000], encoding="utf-8"
        )
        print("\n    Saved HTML head to docs/divar_page_head.html")

        # 8. Test v5 cities endpoint (confirmed 200)
        print("\n[+] Testing v5 cities endpoint...")
        v5_headers = {
            "User-Agent": HEADERS["User-Agent"],
            "Accept": "application/json",
            "Referer": "https://divar.ir/",
        }
        cr = await client.get("https://api.divar.ir/v5/places/cities", headers=v5_headers, timeout=10)
        if cr.status_code == 200:
            cities_data = cr.json()
            print(f"    Cities response keys: {list(cities_data.keys())}")
            # Find Ahvaz city ID
            all_cities = cities_data.get("cities", []) + cities_data.get("top_cities", [])
            ahvaz = [c for c in all_cities if "ahvaz" in str(c).lower() or "اهواز" in str(c)]
            if ahvaz:
                print(f"    Ahvaz entry: {ahvaz[0]}")
            # Save
            (OUTPUT_DIR / "cities_v5.json").write_text(
                json.dumps(cities_data, ensure_ascii=False, indent=2)[:10000],
                encoding="utf-8"
            )


if __name__ == "__main__":
    asyncio.run(run())
