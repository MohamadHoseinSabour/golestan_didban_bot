"""
Use Playwright to intercept real XHR calls to Divar API.
This captures the exact request format used by the browser.
Run: python scripts/playwright_recon.py
"""
import asyncio
import json
import re
from pathlib import Path


async def run():
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("Playwright not installed. Install: pip install playwright && playwright install chromium")
        return

    OUTPUT = Path("docs")
    FIXTURE = Path("tests/fixtures")
    OUTPUT.mkdir(exist_ok=True)
    FIXTURE.mkdir(parents=True, exist_ok=True)

    captured_requests = []
    captured_responses = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="fa-IR",
            extra_http_headers={
                "Accept-Language": "fa,en;q=0.9",
            }
        )
        page = await context.new_page()

        # Capture all API requests
        async def on_request(request):
            url = request.url
            if "api.divar.ir" in url or "divar.ir/v" in url:
                try:
                    post_data = request.post_data
                    captured_requests.append({
                        "url": url,
                        "method": request.method,
                        "headers": dict(request.headers),
                        "body": json.loads(post_data) if post_data else None,
                    })
                    print(f"  [REQ] {request.method} {url}")
                    if post_data:
                        print(f"        Body: {post_data[:200]}")
                except Exception as e:
                    print(f"  [REQ-ERR] {e}")

        async def on_response(response):
            url = response.url
            if "postlist" in url or "posts-v2" in url:
                try:
                    body = await response.body()
                    data = json.loads(body)
                    sanitized = re.sub(r"09\d{9}", "09XXXXXXXXX", json.dumps(data, ensure_ascii=False))
                    captured_responses.append({
                        "url": url,
                        "status": response.status,
                        "data": json.loads(sanitized),
                    })
                    print(f"  [RESP] {response.status} {url} ({len(body)} bytes)")
                except Exception as e:
                    print(f"  [RESP-ERR] {e}")

        page.on("request", on_request)
        page.on("response", on_response)

        target_url = (
            "https://divar.ir/s/ahvaz/real-estate/golestan"
            "?bbox=48.6043%2C31.2658939%2C48.6834793%2C31.3184261"
            "&business-type=personal%2C"
            "&map_free_roaming=true"
        )

        print(f"Navigating to: {target_url}")
        try:
            await page.goto(target_url, timeout=30000, wait_until="networkidle")
        except Exception as e:
            print(f"Navigation timeout (OK, continuing): {e}")

        # Wait for ads to load
        print("Waiting for content...")
        await asyncio.sleep(5)

        # Try to scroll to trigger more loads
        await page.evaluate("window.scrollBy(0, 500)")
        await asyncio.sleep(2)

        # Take screenshot
        await page.screenshot(path="docs/divar_screenshot.png")
        print("Screenshot saved to docs/divar_screenshot.png")

        # Count ad cards
        card_count = await page.locator("[class*='post-card'], [class*='kt-post']").count()
        print(f"Ad cards visible: {card_count}")

        await browser.close()

    print("\n=== Summary ===")
    print(f"API requests captured: {len(captured_requests)}")
    print(f"API responses captured: {len(captured_responses)}")

    # Save captured requests
    if captured_requests:
        (OUTPUT / "captured_requests.json").write_text(
            json.dumps(captured_requests, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print("\nCaptured requests:")
        for req in captured_requests[:10]:
            print(f"  {req['method']} {req['url']}")
            if req["body"]:
                print(f"    Body keys: {list(req['body'].keys()) if isinstance(req['body'], dict) else 'non-dict'}")

    if captured_responses:
        for resp in captured_responses[:3]:
            if "postlist" in resp["url"]:
                fname = "playwright_listing.json"
                (FIXTURE / fname).write_text(
                    json.dumps(resp["data"], ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
                print(f"\nSaved listing fixture: {fname}")
                print(f"Response keys: {list(resp['data'].keys())}")
                break


if __name__ == "__main__":
    asyncio.run(run())
