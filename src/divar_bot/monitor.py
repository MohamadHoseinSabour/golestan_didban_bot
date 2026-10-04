"""
Core monitoring loop and orchestrator.
Manages 60s poll cycles, jitter, baseline initialization, circuit-breaking health alerts,
and integration between DivarClient, Storage, Parser, Classifier, and TelegramBot.
"""

from __future__ import annotations

import asyncio
import random
import time
from datetime import UTC, datetime
from typing import Any

from divar_bot.config import Settings
from divar_bot.divar.classifier import AdClassifier
from divar_bot.divar.client import DivarClient, DivarClientError
from divar_bot.divar.parser import DivarParser
from divar_bot.divar.url_builder import parse_divar_url
from divar_bot.models import AdDetail, ClassifierResult, CycleStats
from divar_bot.storage import Storage
from divar_bot.telegram.bot import TelegramBot
from divar_bot.utils.logging import get_logger
from divar_bot.utils.time import is_too_old

logger = get_logger(__name__)


class MonitorService:
    """Orchestrates periodic scraping, filtering, and notification dispatching."""

    def __init__(
        self,
        settings: Settings,
        storage: Storage,
        divar_client: DivarClient,
        telegram_bot: TelegramBot,
    ) -> None:
        self.settings = settings
        self.storage = storage
        self.client = divar_client
        self.bot = telegram_bot
        self.classifier = AdClassifier(agency_keywords=settings.agency_keywords)

        self._running = False
        self._lock = asyncio.Lock()
        self._consecutive_failures = 0
        self._health_alert_sent = False
        self._is_first_run = True

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """Start the monitor loop."""
        self._running = True
        logger.info("monitor_service_started")

        # Check existing ad count to detect if this is first run ever
        status_counts = await self.storage.count_by_status()
        total_tracked = sum(status_counts.values())
        if total_tracked > 0:
            self._is_first_run = False
            logger.info("monitor_resuming_with_existing_db", tracked_ads=total_tracked)
        else:
            logger.info("monitor_first_run_detected", notify_count=self.settings.notify_on_first_run)

        while self._running:
            try:
                # Only execute cycle if bot is not paused
                if not self.bot.is_paused:
                    async with self._lock:
                        await self.run_cycle()
            except Exception as e:
                logger.error("monitor_unhandled_cycle_exception", error=str(e), exc_info=True)

            # Sleep with jitter: poll_interval ± jitter
            jitter = random.uniform(
                -self.settings.jitter_seconds,
                self.settings.jitter_seconds,
            )
            sleep_duration = max(5.0, self.settings.poll_interval_seconds + jitter)
            logger.debug("monitor_sleeping", seconds=round(sleep_duration, 1))

            try:
                await asyncio.sleep(sleep_duration)
            except asyncio.CancelledError:
                break

    def stop(self) -> None:
        """Signal the monitor loop to stop."""
        self._running = False
        logger.info("monitor_service_stopping")

    async def run_cycle(self) -> CycleStats:
        """Execute a single monitoring cycle across all configured URLs."""
        t_start = time.time()
        cycle_id = await self.storage.start_cycle()
        stats = CycleStats(cycle_id=cycle_id, started_at=datetime.now(tz=UTC))

        try:
            for url in self.settings.divar_urls:
                await self._process_url(url, stats)

            # Successfully completed cycle
            if self._health_alert_sent:
                # Recovered from previous failure!
                logger.info("monitor_recovered_from_outage")
                await self.bot.send_health_alert(
                    "✅ <b>اتصال به دیوار بازیابی شد</b>\nپایش آگهی‌ها به حالت عادی بازگشت."
                )
                self._health_alert_sent = False

            self._consecutive_failures = 0
            self._is_first_run = False

        except DivarClientError as client_err:
            stats.error = str(client_err)
            self._consecutive_failures += 1
            logger.warning(
                "monitor_cycle_client_error",
                consecutive_failures=self._consecutive_failures,
                error=str(client_err),
            )

            # Health alert protocol: if >= 3 consecutive failures, send ONE alert
            if self._consecutive_failures >= 3 and not self._health_alert_sent:
                self._health_alert_sent = True
                await self.bot.send_health_alert(
                    f"⚠️ <b>خطا در پایش دیوار</b>\n\n"
                    f"ارتباط با دیوار در {self._consecutive_failures} چرخه متوالی با خطا مواجه شد:\n"
                    f"<code>{client_err}</code>\n\n"
                    f"ربات در حال تلاش مجدد است. پس از رفع مشکل اطلاع داده خواهد شد."
                )

        except Exception as err:
            stats.error = str(err)
            self._consecutive_failures += 1
            logger.error("monitor_cycle_general_error", error=str(err), exc_info=True)

        finally:
            t_end = time.time()
            stats.ended_at = datetime.now(tz=UTC)
            stats.duration_seconds = round(t_end - t_start, 2)
            await self.storage.end_cycle(stats)
            logger.info(
                "monitor_cycle_finished",
                cycle_id=cycle_id,
                duration=stats.duration_seconds,
                seen=stats.ads_seen,
                new=stats.ads_new,
                personal=stats.ads_personal,
                sent=stats.ads_sent,
                skipped_agency=stats.ads_skipped_agency,
                error=stats.error,
            )

        return stats

    async def _process_url(self, url: str, stats: CycleStats) -> None:
        """Process listings from a single search URL."""
        search_params = parse_divar_url(url, use_bbox=self.settings.use_bbox)
        post_widgets = await self.client.fetch_listings(search_params)
        stats.ads_seen += len(post_widgets)

        # First run baseline logic
        if self._is_first_run:
            await self._handle_first_run(post_widgets, stats)
            return

        # Normal monitoring logic
        sent_this_cycle = 0

        for widget in post_widgets:
            if sent_this_cycle >= self.settings.max_send_per_cycle:
                logger.info("max_send_per_cycle_reached", count=sent_this_cycle)
                break

            data = widget.get("data", {})
            token = data.get("token")
            if not token:
                continue

            # Check deduplication
            if await self.storage.is_known(token):
                continue

            stats.ads_new += 1
            logger.info("new_ad_discovered", token=token)

            # Fetch detail ONLY for new ad
            try:
                detail_json = await self.client.fetch_detail(token)
            except Exception as e:
                logger.error("detail_fetch_failed", token=token, error=str(e))
                stats.ads_failed += 1
                await self.storage.mark_failed(token, f"Detail fetch failed: {e}")
                continue

            # Classify
            result, reason = self.classifier.classify(detail_json)
            if result == ClassifierResult.AGENCY:
                stats.ads_skipped_agency += 1
                logger.info("skipped_agency_listing", token=token, reason=reason)
                await self.storage.mark_skipped_agency(token, reason)
                continue

            stats.ads_personal += 1
            ad = DivarParser.parse_detail(token, detail_json)
            await self.storage.mark_seen(ad)

            # Check age limit (prevent notification storm after long bot downtime)
            if is_too_old(ad.created_at, self.settings.max_ad_age_minutes):
                logger.info("skipped_old_listing", token=token, age_minutes=self.settings.max_ad_age_minutes)
                continue

            # Price & area optional filters from config
            if not self._passes_user_filters(ad):
                logger.info("skipped_by_user_filters", token=token)
                continue

            # Send Telegram notification
            msg_ids = await self.bot.send_notification(ad)
            if msg_ids:
                sent_this_cycle += 1
                stats.ads_sent += 1
                await self.storage.mark_notified(token, msg_ids[0])
                logger.info("ad_notified_successfully", token=token, msg_ids=msg_ids)
            else:
                stats.ads_failed += 1
                await self.storage.mark_failed(token, "Telegram delivery failed")

    async def _handle_first_run(self, post_widgets: list[dict[str, Any]], stats: CycleStats) -> None:
        """Handle first run baseline without spamming users."""
        notify_count = self.settings.notify_on_first_run
        logger.info("handling_first_run_baseline", total_posts=len(post_widgets), notify_count=notify_count)

        for i, widget in enumerate(post_widgets):
            token = widget.get("data", {}).get("token")
            if not token:
                continue

            if await self.storage.is_known(token):
                continue

            # If user configured notify_on_first_run > 0, notify the latest N ads
            if i < notify_count:
                try:
                    detail_json = await self.client.fetch_detail(token)
                    result, reason = self.classifier.classify(detail_json)
                    if result == ClassifierResult.PERSONAL:
                        ad = DivarParser.parse_detail(token, detail_json)
                        await self.storage.mark_seen(ad)
                        msg_ids = await self.bot.send_notification(ad)
                        if msg_ids:
                            await self.storage.mark_notified(token, msg_ids[0])
                            stats.ads_sent += 1
                    else:
                        await self.storage.mark_skipped_agency(token, reason)
                except Exception as e:
                    logger.error("first_run_notification_error", token=token, error=str(e))
            else:
                # Mark as seen without notifying (baseline silently recorded)
                summary = DivarParser.parse_listing_widget(widget)
                if summary:
                    from divar_bot.models import Ad
                    baseline_ad = Ad(token=token, title=summary.get("title"))
                    await self.storage.mark_seen(baseline_ad)

    def _passes_user_filters(self, ad: AdDetail) -> bool:
        """Check optional custom user filters for price and area."""
        if self.settings.min_price and ad.total_price and ad.total_price < self.settings.min_price:
            return False
        if self.settings.max_price and ad.total_price and ad.total_price > self.settings.max_price:
            return False
        if self.settings.min_area_m2 and ad.area_m2 and ad.area_m2 < self.settings.min_area_m2:
            return False
        if self.settings.max_area_m2 and ad.area_m2 and ad.area_m2 > self.settings.max_area_m2:
            return False
        return True
