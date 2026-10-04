"""
Application main entrypoint and CLI runner.
Handles lifecycle, signal interception, and concurrently runs the Telegram Bot and MonitorService.
"""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys

from divar_bot.config import get_settings
from divar_bot.divar.client import DivarClient
from divar_bot.monitor import MonitorService
from divar_bot.storage import Storage
from divar_bot.telegram.bot import TelegramBot
from divar_bot.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


async def run_bot(dry_run: bool = False) -> None:
    """Initialize all services and run the monitoring loop and Telegram bot."""
    settings = get_settings()

    setup_logging(
        level=settings.log_level,
        log_dir=settings.log_dir,
        max_file_mb=settings.log_max_file_mb,
        backup_count=settings.log_backup_count,
    )

    logger.info(
        "divar_alert_bot_starting",
        urls=settings.divar_urls,
        poll_interval=settings.poll_interval_seconds,
        dry_run=dry_run,
    )

    storage = Storage(db_path=settings.db_path)
    await storage.open()

    divar_client = DivarClient(
        proxy_url=settings.divar_proxy_url,
    )
    await divar_client.open()

    telegram_bot = TelegramBot(settings=settings)

    monitor = MonitorService(
        settings=settings,
        storage=storage,
        divar_client=divar_client,
        telegram_bot=telegram_bot,
    )
    telegram_bot.monitor_service = monitor

    if dry_run:
        logger.info("running_single_dry_run_cycle")
        # Initialize bot without starting polling
        try:
            stats = await monitor.run_cycle()
            print("\n=== Dry Run Results ===")
            print(f"Cycle ID: {stats.cycle_id}")
            print(f"Ads Seen: {stats.ads_seen}")
            print(f"Ads New: {stats.ads_new}")
            print(f"Personal Ads: {stats.ads_personal}")
            print(f"Skipped Agency: {stats.ads_skipped_agency}")
            print(f"Duration: {stats.duration_seconds}s")
            if stats.error:
                print(f"Error: {stats.error}")
        finally:
            await divar_client.close()
            await storage.close()
        return

    # Real bot execution
    await telegram_bot.initialize()

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _shutdown_signal_handler() -> None:
        logger.info("shutdown_signal_received")
        monitor.stop()
        stop_event.set()

    # Register OS signals
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _shutdown_signal_handler)

    try:
        await telegram_bot.start()
        monitor_task = asyncio.create_task(monitor.start())

        if sys.platform == "win32":
            # On Windows, keep alive until interrupted
            while not stop_event.is_set():
                await asyncio.sleep(0.5)
        else:
            await stop_event.wait()

        # Cancel monitor task and wait
        monitor.stop()
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("keyboard_interrupt_shutting_down")
    finally:
        logger.info("closing_resources")
        await telegram_bot.stop()
        await divar_client.close()
        await storage.close()
        logger.info("divar_alert_bot_shutdown_complete")


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Divar Real-Estate Alert Telegram Bot (Golestan Ahvaz)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run a single monitoring cycle without telegram polling and print stats",
    )
    args = parser.parse_args()

    try:
        asyncio.run(run_bot(dry_run=args.dry_run))
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)


if __name__ == "__main__":
    main()
