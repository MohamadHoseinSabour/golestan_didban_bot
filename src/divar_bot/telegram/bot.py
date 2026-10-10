"""
Telegram Bot manager and command handlers.
Implements commands (/start, /status, /pause, /resume, /last) and notification sending.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import RetryAfter, TelegramError
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
from telegram.request import HTTPXRequest

from divar_bot.config import Settings
from divar_bot.models import AdDetail
from divar_bot.telegram.formatter import format_ad_message
from divar_bot.telegram.security import restricted
from divar_bot.utils.logging import get_logger
from divar_bot.utils.persian import to_persian_digits

if TYPE_CHECKING:
    from divar_bot.monitor import MonitorService

logger = get_logger(__name__)


class TelegramBot:
    """Manages the Telegram Bot application, handlers, and outgoing notifications."""

    def __init__(
        self,
        settings: Settings,
        monitor_service: MonitorService | None = None,
    ) -> None:
        self.settings = settings
        self.monitor_service = monitor_service
        self.app: Any | None = None
        self._is_paused = False

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    def set_paused(self, paused: bool) -> None:
        self._is_paused = paused

    async def initialize(self) -> None:
        """Build and configure the python-telegram-bot Application."""
        if not self.settings.telegram_bot_token:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN is required to run the bot. "
                "Please set it in your .env file."
            )
        request_kwargs: dict[str, Any] = {
            "connect_timeout": 10.0,
            "read_timeout": 20.0,
        }
        if self.settings.telegram_proxy_url:
            request_kwargs["proxy_url"] = self.settings.telegram_proxy_url
            logger.info("telegram_using_proxy", proxy=self.settings.telegram_proxy_url)

        request = HTTPXRequest(**request_kwargs)

        builder = ApplicationBuilder().token(self.settings.telegram_bot_token).request(request)

        if self.settings.telegram_api_base_url:
            builder = builder.base_url(self.settings.telegram_api_base_url)
            logger.info("telegram_using_custom_base_url", base_url=self.settings.telegram_api_base_url)

        self.app = builder.build()
        self._register_handlers()
        await self.app.initialize()

    def _register_handlers(self) -> None:
        assert self.app is not None
        get_allowed_ids = lambda: self.settings.allowed_user_ids  # noqa: E731

        # Handlers protected with @restricted decorator
        @restricted(get_allowed_ids)
        async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            text = (
                "🤖 <b>دیدبان املاک گلستان اهواز</b> فعال است.\n\n"
                "📌 آگهی‌های جدید شخصی هر ۶۰ ثانیه پایش شده و بلافاصله برای شما ارسال می‌شوند.\n\n"
                "دستورات:\n"
                "▫️ /status — وضعیت فعلی ربات و آخرین چرخه\n"
                "▫️ /last — نمایش ۵ آگهی آخر ارسال‌شده\n"
                "▫️ /pause — توقف موقت پایش\n"
                "▫️ /resume — ادامه پایش"
            )
            if update.effective_message:
                await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)

        @restricted(get_allowed_ids)
        async def handle_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            status_text = "🟢 در حال پایش" if not self._is_paused else "⏸ متوقف‌شده (Pause)"
            cycle_info = "نامشخص"
            counts = {}
            if self.monitor_service:
                counts = await self.monitor_service.storage.count_by_status()
                last_c = await self.monitor_service.storage.get_last_cycle()
                if last_c:
                    cycle_info = (
                        f"چرخه شماره {to_persian_digits(last_c.get('id', 0))}\n"
                        f"▫️ دیده‌شده: {to_persian_digits(last_c.get('ads_seen', 0))}\n"
                        f"▫️ جدید: {to_persian_digits(last_c.get('ads_new', 0))}\n"
                        f"▫️ ارسال‌شده: {to_persian_digits(last_c.get('ads_sent', 0))}"
                    )

            notified_count = counts.get("notified", 0)
            seen_count = counts.get("seen", 0)

            msg = (
                f"📊 <b>وضعیت ربات</b>:\n\n"
                f"▫️ وضعیت: {status_text}\n"
                f"▫️ کل آگهی‌های ارسال‌شده: {to_persian_digits(notified_count)}\n"
                f"▫️ کل دیده‌شده در دیتابیس: {to_persian_digits(seen_count)}\n\n"
                f"<b>آخرین چرخه:</b>\n{cycle_info}"
            )
            if update.effective_message:
                await update.effective_message.reply_text(msg, parse_mode=ParseMode.HTML)

        @restricted(get_allowed_ids)
        async def handle_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            self._is_paused = True
            if update.effective_message:
                await update.effective_message.reply_text("⏸ پایش آگهی‌ها موقتاً متوقف شد. برای ادامه /resume را ارسال کنید.")

        @restricted(get_allowed_ids)
        async def handle_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            self._is_paused = False
            if update.effective_message:
                await update.effective_message.reply_text("▶️ پایش آگهی‌ها مجدداً فعال شد.")

        @restricted(get_allowed_ids)
        async def handle_last(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            if not self.monitor_service:
                if update.effective_message:
                    await update.effective_message.reply_text("اطلاعاتی در دسترس نیست.")
                return

            recent = await self.monitor_service.storage.get_recent_notified(limit=5)
            if not recent:
                if update.effective_message:
                    await update.effective_message.reply_text("هنوز آگهی جدیدی ارسال نشده است.")
                return

            lines = ["📋 <b>۵ آگهی آخر ارسال‌شده:</b>\n"]
            for i, item in enumerate(recent, 1):
                title = item.get("title") or "بدون عنوان"
                url = item.get("url") or f"https://divar.ir/v/{item.get('token')}"
                phone = item.get("contact_phone")
                phone_suffix = f" (📞 <code>{phone}</code>)" if phone else ""
                lines.append(f"{to_persian_digits(i)}. <a href=\"{url}\">{title}</a>{phone_suffix}")

            if update.effective_message:
                await update.effective_message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML, disable_web_page_preview=True)

        self.app.add_handler(CommandHandler("start", handle_start))
        self.app.add_handler(CommandHandler("status", handle_status))
        self.app.add_handler(CommandHandler("pause", handle_pause))
        self.app.add_handler(CommandHandler("resume", handle_resume))
        self.app.add_handler(CommandHandler("last", handle_last))

    async def start(self) -> None:
        """Start receiving updates."""
        assert self.app is not None
        await self.app.start()
        if self.app.updater is not None:
            await self.app.updater.start_polling(drop_pending_updates=True)
        logger.info("telegram_bot_started")

    async def stop(self) -> None:
        """Stop polling and close application."""
        if self.app:
            if self.app.updater and self.app.updater.running:
                await self.app.updater.stop()
            if self.app.running:
                await self.app.stop()
            await self.app.shutdown()
            logger.info("telegram_bot_stopped")

    async def send_notification(self, ad: AdDetail) -> list[int]:
        """
        Send ad notification to all allowed user IDs.
        Returns list of successful Telegram message IDs.
        """
        if not self.app or not self.app.bot:
            raise RuntimeError("Telegram bot is not initialized")

        html_text, keyboard = format_ad_message(ad)
        successful_message_ids: list[int] = []

        thumbnail = ad.thumbnail_url if self.settings.send_thumbnail else None
        cached_photo_file_id: str | None = None

        for user_id in self.settings.allowed_user_ids:
            try:
                sent_msg = None
                photo_payload = cached_photo_file_id or thumbnail

                # 1. Try sending photo with caption if thumbnail/cached_file_id is available
                if photo_payload:
                    try:
                        sent_msg = await self.app.bot.send_photo(
                            chat_id=user_id,
                            photo=photo_payload,
                            caption=html_text,
                            parse_mode=ParseMode.HTML,
                            reply_markup=keyboard,
                        )
                        # Cache the telegram file_id so subsequent users receive it instantly
                        if sent_msg and sent_msg.photo:
                            cached_photo_file_id = sent_msg.photo[-1].file_id
                    except TelegramError as photo_err:
                        logger.warning(
                            "telegram_photo_send_failed_fallback_text",
                            user_id=user_id,
                            error=str(photo_err),
                            token=ad.token,
                        )

                # 2. If photo was not sent (or failed), fallback to HTML text message
                if sent_msg is None:
                    sent_msg = await self.app.bot.send_message(
                        chat_id=user_id,
                        text=html_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=keyboard,
                        disable_web_page_preview=False,
                    )

                successful_message_ids.append(sent_msg.message_id)
                logger.info(
                    "telegram_ad_sent_to_user",
                    user_id=user_id,
                    message_id=sent_msg.message_id,
                    token=ad.token,
                )

            except RetryAfter as rate_err:
                logger.warning("telegram_rate_limited", user_id=user_id, retry_after=rate_err.retry_after)
                sleep_s = (
                    float(rate_err.retry_after.total_seconds())
                    if hasattr(rate_err.retry_after, "total_seconds")
                    else float(rate_err.retry_after)
                )
                await asyncio.sleep(sleep_s)
                # Retry once as text message
                try:
                    retry_msg = await self.app.bot.send_message(
                        chat_id=user_id,
                        text=html_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=keyboard,
                    )
                    successful_message_ids.append(retry_msg.message_id)
                    logger.info(
                        "telegram_ad_sent_to_user_after_retry",
                        user_id=user_id,
                        message_id=retry_msg.message_id,
                        token=ad.token,
                    )
                except Exception as retry_e:
                    logger.error("telegram_send_retry_failed", user_id=user_id, error=str(retry_e))

            except TelegramError as tg_err:
                err_msg = str(tg_err)
                if "bot can't initiate conversation" in err_msg.lower() or "chat not found" in err_msg.lower():
                    logger.warning(
                        "telegram_user_must_start_bot_first",
                        user_id=user_id,
                        hint=f"User {user_id} has not clicked /start on the bot yet.",
                        error=err_msg,
                    )
                else:
                    logger.error("telegram_send_error", user_id=user_id, error=err_msg)

            except Exception as unhandled_err:
                logger.error("telegram_send_unhandled_error", user_id=user_id, error=str(unhandled_err))

            # Small pause between distinct recipients to respect Telegram rate limits
            await asyncio.sleep(0.05)

        return successful_message_ids

    async def send_health_alert(self, text: str) -> None:
        """Send health/outage warning or recovery notification to users."""
        if not self.app or not self.app.bot:
            return

        for user_id in self.settings.allowed_user_ids:
            try:
                msg = await self.app.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode=ParseMode.HTML,
                )
                logger.info("telegram_health_alert_sent", user_id=user_id, message_id=msg.message_id)
            except Exception as e:
                logger.error("telegram_health_alert_failed", user_id=user_id, error=str(e))

            await asyncio.sleep(0.05)
