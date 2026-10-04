"""
Dry run script:
Executes 1 cycle of Divar scraping, classification, and formatting,
and prints the resulting Telegram messages to stdout without calling the Telegram API.
"""
import asyncio
import sys

# Ensure UTF-8 console output
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from divar_bot.config import get_settings
from divar_bot.divar.classifier import AdClassifier
from divar_bot.divar.client import DivarClient
from divar_bot.divar.parser import DivarParser
from divar_bot.divar.url_builder import parse_divar_url
from divar_bot.telegram.formatter import format_ad_message


async def run_dry_run():
    print("=" * 60)
    print("Golestan Didban Bot — Dry Run (No Telegram Sends)")
    print("=" * 60)

    settings = get_settings()
    url = settings.divar_urls[0] if settings.divar_urls else None
    if not url:
        print("Error: No divar_urls configured in config.yaml / .env")
        return

    print(f"Target URL: {url}\n")
    search_params = parse_divar_url(url, use_bbox=settings.use_bbox)
    classifier = AdClassifier(agency_keywords=settings.agency_keywords)

    async with DivarClient(proxy_url=settings.divar_proxy_url) as client:
        print("1. Fetching search listings from Divar API...")
        widgets = await client.fetch_listings(search_params)
        print(f"   Found {len(widgets)} listings on page 1.\n")

        print("2. Fetching details and parsing first 3 ads...\n")
        sample_widgets = widgets[:3]

        for i, w in enumerate(sample_widgets, 1):
            token = w.get("data", {}).get("token")
            if not token:
                continue

            print(f"--- Ad #{i} [Token: {token}] ---")
            detail_data = await client.fetch_detail(token)
            result, reason = classifier.classify(detail_data)

            print(f"Classification: {result.value.upper()} (Reason: {reason})")

            ad = DivarParser.parse_detail(token, detail_data)
            msg_text, _ = format_ad_message(ad)

            print("\nGenerated Telegram Message:")
            print("----------------------------------------")
            print(msg_text)
            print("----------------------------------------\n")
            await asyncio.sleep(0.5)

    print("Dry run completed successfully.")

if __name__ == "__main__":
    asyncio.run(run_dry_run())
