"""
Security and access control for the Telegram bot.
Enforces ALLOWED_USER_IDS: unauthorized users receive zero response (stealth mode)
and are strictly logged for auditing.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from divar_bot.utils.logging import get_logger

logger = get_logger(__name__)


def is_user_allowed(
    user_id: int | str | None,
    allowed_ids: list[int] | Callable[[], list[int]],
) -> bool:
    """Return True if user_id is in allowed_ids list."""
    if user_id is None:
        return False

    resolved_ids: list[int] = allowed_ids() if callable(allowed_ids) else allowed_ids
    if not resolved_ids:
        # If no users configured, fail safe: allow no one
        return False

    try:
        uid = int(user_id)
        return uid in [int(x) for x in resolved_ids]
    except (ValueError, TypeError):
        return False


def restricted(allowed_ids: list[int] | Callable[[], list[int]]) -> Callable[..., Any]:
    """
    Decorator for python-telegram-bot handler functions.
    Silently ignores updates from unauthorized users.
    Supports either a static list of IDs or a callable returning current IDs.
    """
    def decorator(
        func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, Any]]
    ) -> Callable[[Update, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, Any]]:
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
            user = update.effective_user
            user_id = user.id if user else None

            if user_id is None or not is_user_allowed(user_id, allowed_ids):
                logger.warning(
                    "unauthorized_access_attempt",
                    user_id=user_id,
                    username=user.username if user else None,
                    message_text=update.effective_message.text if update.effective_message else None,
                )
                # Silent drop — no response sent back to the unauthorized user
                return None

            return await func(update, context)

        return wrapper

    return decorator
