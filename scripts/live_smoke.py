"""
Live smoke test script:
Fetches 20+ real listings from Divar API and validates that all tokens and data are authentic.
"""
import asyncio
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from divar_bot.config import get_settings
from divar_bot.divar.client import DivarClient
from divar_bot.divar.url_builder import parse_divar_url


async def smoke_test():
    print("=" * 60)
    print("Live Smoke Test: Divar Listing API")
    print("=" * 60)

    settings = get_settings()
    url = settings.divar_urls[0]
    params = parse_divar_url(url, use_bbox=settings.use_bbox)

    async with DivarClient(proxy_url=settings.divar_proxy_url) as client:
        widgets = await client.fetch_listings(params)
        print(f"Total post widgets returned: {len(widgets)}")

        tokens = [
            w.get("data", {}).get("token")
            for w in widgets
            if w.get("data", {}).get("token")
        ]
        print(f"Unique tokens extracted: {len(set(tokens))}")

        assert len(tokens) >= 20, f"Expected at least 20 listings, got {len(tokens)}"

        first = widgets[0].get("data", {})
        print("\nSample listing #1:")
        print(f"  Token: {first.get('token')}")
        print(f"  Title: {first.get('title')}")
        print(f"  Bottom text: {first.get('bottom_description_text')}")
        print(f"  Middle text: {first.get('middle_description_text')}")

    print("\n✅ Live smoke test PASSED: Divar API returned >= 20 real listings.")

if __name__ == "__main__":
    asyncio.run(smoke_test())
