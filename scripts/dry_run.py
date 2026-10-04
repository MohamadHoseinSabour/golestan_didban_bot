"""
Dry run script:
Inspects the latest 20 listings from Divar, checks SQLite database deduplication,
validates personal vs agency classification, and filters out old/bumped ads.
Simulates sending Telegram notifications without calling the live Telegram API.
"""
from __future__ import annotations

import asyncio
import sys

# Ensure UTF-8 console output
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from divar_bot.config import get_settings
from divar_bot.divar.classifier import AdClassifier, ClassifierResult
from divar_bot.divar.client import DivarClient
from divar_bot.divar.parser import DivarParser
from divar_bot.divar.url_builder import parse_divar_url
from divar_bot.storage import Storage
from divar_bot.telegram.formatter import format_ad_message
from divar_bot.utils.time import is_too_old


async def run_dry_run() -> None:
    print("=" * 70)
    print("دیدبان املاک گلستان — اجرای آزمایشی (بررسی ۲۰ آگهی آخر + دیتابیس)")
    print("=" * 70)

    settings = get_settings()
    url = settings.divar_urls[0] if settings.divar_urls else None
    if not url:
        print("خطا: هیچ لینکی در config.yaml یا .env تعریف نشده است.")
        return

    print(f"🔗 آدرس مورد بررسی: {url}")
    print(f"⏱ سقف سن آگهی معتبر: {settings.max_ad_age_minutes} دقیقه")
    print(f"💾 مسیر پایگاه داده: {settings.db_path}\n")

    storage = Storage(settings.db_path)
    await storage.open()

    search_params = parse_divar_url(url, use_bbox=settings.use_bbox)
    classifier = AdClassifier(agency_keywords=settings.agency_keywords)

    stats = {
        "total_checked": 0,
        "already_known": 0,
        "skipped_agency": 0,
        "skipped_old": 0,
        "valid_new": 0,
    }

    try:
        async with DivarClient(proxy_url=settings.divar_proxy_url) as client:
            print("۱. دریافت لیست آگهی‌های اخیر از دیوار...")
            widgets = await client.fetch_listings(search_params)
            total_found = len(widgets)
            print(f"   تعداد {total_found} آگهی در صفحه اول یافت شد.\n")

            limit = min(20, total_found)
            print(f"۲. بررسی {limit} آگهی اول به همراه تطبیق با دیتابیس و فیلتر زمان...\n")
            target_widgets = widgets[:limit]

            for i, w in enumerate(target_widgets, 1):
                stats["total_checked"] += 1
                token = w.get("data", {}).get("token")
                w_title = w.get("data", {}).get("title", "بدون عنوان")
                if not token:
                    continue

                print(f"[{i:02d}/{limit:02d}] آگهی: «{w_title}» (توکن: {token})")

                # ۱. بررسی تکراری بودن در دیتابیس (Deduplication)
                is_known = await storage.is_known(token)
                if is_known:
                    stats["already_known"] += 1
                    print("   ⏭ وضعیت: [رد شد - تکراری] این آگهی قبلاً در دیتابیس ثبت شده است.\n")
                    continue

                # ۲. دریافت جزئیات آگهی جدید
                try:
                    detail_data = await client.fetch_detail(token)
                except Exception as e:
                    print(f"   ⚠️ خطا در دریافت جزئیات: {e}\n")
                    continue

                # ۳. بررسی بنگاه یا شخصی بودن
                result, reason = classifier.classify(detail_data)
                if result == ClassifierResult.AGENCY:
                    stats["skipped_agency"] += 1
                    print(f"   ⏭ وضعیت: [رد شد - مشاور املاک/بنگاه] دلیل: {reason}\n")
                    continue

                # ۴. تحلیل زمان و بررسی کهنگی (نردبان‌شده یا زمان گذشته)
                ad = DivarParser.parse_detail(token, detail_data)
                if is_too_old(ad.created_at, settings.max_ad_age_minutes):
                    stats["skipped_old"] += 1
                    print(
                        f"   ⏭ وضعیت: [رد شد - قدیمی/نردبان‌شده] تاریخ انتشار: {ad.created_at_relative} "
                        f"(بیش از {settings.max_ad_age_minutes} دقیقه گذشته)\n"
                    )
                    continue

                # ۵. آگهی جدید، معتبر و شخصی
                stats["valid_new"] += 1
                msg_text, _ = format_ad_message(ad)
                print(f"   ✅ وضعیت: [تأیید شد - آگهی جدید شخصی] تاریخ: {ad.created_at_relative}")
                print("   📨 متن پیام تلگرامی:")
                print("   " + "-" * 40)
                indented_msg = "\n   ".join(msg_text.splitlines())
                print(f"   {indented_msg}")
                print("   " + "-" * 40 + "\n")

                await asyncio.sleep(0.5)

    finally:
        await storage.close()

    print("=" * 70)
    print("📊 خلاصه نتیجه بررسی اجرای آزمایشی:")
    print(f" - کل آگهی‌های بررسی شده: {stats['total_checked']}")
    print(f" - رد شده به دلیل تکراری بودن در دیتابیس: {stats['already_known']}")
    print(f" - رد شده به دلیل مشاور املاک/بنگاه بودن: {stats['skipped_agency']}")
    print(f" - رد شده به دلیل قدیمی/نردبان‌بودن (بیش از ۳ ساعت): {stats['skipped_old']}")
    print(f" - آگهی‌های جدید، تازه و شخصی (آماده ارسال): {stats['valid_new']}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_dry_run())
