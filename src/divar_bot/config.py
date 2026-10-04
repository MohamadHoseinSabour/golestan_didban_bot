"""
Application configuration via pydantic-settings.
Reads from .env file and/or environment variables.
config.yaml provides defaults; env vars override everything.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# YAML loader helper
# ---------------------------------------------------------------------------
def _load_yaml(path: Path) -> dict[str, Any]:
    if path.exists():
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
    return {}


_CONFIG_PATH = Path(os.getenv("CONFIG_PATH", "config.yaml"))
_YAML = _load_yaml(_CONFIG_PATH)


def _y(*keys: str, default: Any = None) -> Any:
    """Navigate nested YAML dict with dotted keys."""
    d: Any = _YAML
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
    return d if d is not None else default


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Telegram ---
    telegram_bot_token: str = Field(
        default="",
        description="Telegram bot token from BotFather",
    )
    allowed_user_ids: list[int] = Field(
        default_factory=list,
        description="Comma-separated list of allowed Telegram user IDs",
    )
    # Proxy for Telegram (e.g. socks5://user:pass@host:port)
    telegram_proxy_url: str | None = Field(default=None)
    # Custom Telegram API base URL (for reverse proxy)
    telegram_api_base_url: str | None = Field(default=None)

    # --- Divar ---
    divar_urls: list[str] = Field(
        default_factory=lambda: _y("divar", "urls", default=[]),
        description="One or more Divar search page URLs",
    )
    divar_proxy_url: str | None = Field(default=None)
    use_bbox: bool = Field(
        default=bool(_y("divar", "use_bbox", default=True)),
    )
    poll_interval_seconds: int = Field(
        default=int(_y("divar", "poll_interval_seconds", default=60)),
    )
    jitter_seconds: int = Field(
        default=int(_y("divar", "jitter_seconds", default=5)),
    )
    max_ad_age_minutes: int = Field(
        default=int(_y("divar", "max_ad_age_minutes", default=180)),
    )
    max_send_per_cycle: int = Field(
        default=int(_y("divar", "max_send_per_cycle", default=20)),
    )
    notify_on_first_run: int = Field(
        default=int(_y("divar", "notify_on_first_run", default=0)),
    )
    agency_keywords: list[str] = Field(
        default_factory=lambda: _y(
            "divar", "agency_keywords",
            default=["املاک", "مشاور", "بنگاه", "مجتمع", "آژانس", "گروه", "شرکت"]
        ),
    )
    send_thumbnail: bool = Field(
        default=bool(_y("divar", "send_thumbnail", default=True)),
    )
    # Optional price/area filters (None = no filter)
    min_price: int | None = Field(default=_y("divar", "min_price"))
    max_price: int | None = Field(default=_y("divar", "max_price"))
    min_area_m2: float | None = Field(default=_y("divar", "min_area_m2"))
    max_area_m2: float | None = Field(default=_y("divar", "max_area_m2"))

    # --- Database ---
    db_path: str = Field(
        default=str(_y("database", "path", default="data/divar_bot.db")),
    )

    # --- Logging ---
    log_level: str = Field(default=str(_y("logging", "level", default="INFO")))
    log_dir: str = Field(default=str(_y("logging", "log_dir", default="logs")))
    log_max_file_mb: int = Field(
        default=int(_y("logging", "max_file_mb", default=10)),
    )
    log_backup_count: int = Field(
        default=int(_y("logging", "backup_count", default=5)),
    )

    # --- Telegram formatting ---
    timezone: str = Field(
        default=str(_y("telegram", "timezone", default="Asia/Tehran")),
    )

    @field_validator("allowed_user_ids", mode="before")
    @classmethod
    def parse_user_ids(cls, v: object) -> list[int]:
        if isinstance(v, str):
            return [int(uid.strip()) for uid in v.split(",") if uid.strip()]
        if isinstance(v, int):
            return [v]
        if isinstance(v, list):
            return [int(x) for x in v]
        return []

    @field_validator("divar_urls", mode="before")
    @classmethod
    def parse_urls(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return [u.strip() for u in v.split(",") if u.strip()]
        if isinstance(v, list):
            return [str(u) for u in v]
        return []


_settings_instance: Settings | None = None


def get_settings() -> Settings:
    """Return cached Settings instance."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
