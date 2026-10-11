"""
Application configuration via pydantic-settings.
Reads from .env file and/or environment variables.
config.yaml provides defaults; env vars override everything.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

_DIGITS_TO_ASCII = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


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
        env_file=(".env", ".emv"),
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
        default_factory=lambda: _y("telegram", "allowed_user_ids", default=[]),
        validation_alias=AliasChoices(
            "allowed_user_ids",
            "allowed_user_id",
            "telegram_user_ids",
            "telegram_user_id",
            "user_ids",
            "user_id",
        ),
        description="Comma-separated list of allowed Telegram user IDs",
    )
    # Proxy for Telegram (e.g. socks5://user:pass@host:port)
    telegram_proxy_url: str | None = Field(default=None)
    # Custom Telegram API base URL (for reverse proxy)
    telegram_api_base_url: str | None = Field(default=None)

    # --- Divar ---
    divar_urls: list[str] = Field(
        default_factory=lambda: _y("divar", "urls", default=[]),
        validation_alias=AliasChoices(
            "divar_urls",
            "divar_url",
            "divar_search_urls",
            "divar_search_url",
            "search_urls",
            "search_url",
        ),
        description="One or more Divar search page URLs",
    )
    divar_proxy_url: str | None = Field(default=None)
    divar_auth_token: str | None = Field(
        default=_y("divar", "auth_token", default=None),
        description="Optional Divar session token or cookie for official contact info API",
    )
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
            s = v.strip().translate(_DIGITS_TO_ASCII)
            matches = re.findall(r"-?\d+", s)
            return list(dict.fromkeys(int(m) for m in matches))
        if isinstance(v, (int, float)):
            return [int(v)]
        if isinstance(v, (list, tuple, set)):
            res_list: list[int] = []
            for x in v:
                if isinstance(x, str):
                    clean = x.strip().translate(_DIGITS_TO_ASCII)
                    matches = re.findall(r"-?\d+", clean)
                    res_list.extend(int(m) for m in matches)
                elif isinstance(x, (int, float)):
                    res_list.append(int(x))
            return list(dict.fromkeys(res_list))
        return []

    @field_validator("divar_urls", mode="before")
    @classmethod
    def parse_urls(cls, v: object) -> list[str]:
        if isinstance(v, str):
            s = v.strip()
            # 1. Try parsing valid JSON array if bracketed
            if s.startswith("[") and s.endswith("]"):
                try:
                    import json
                    parsed = json.loads(s)
                    if isinstance(parsed, list):
                        return list(dict.fromkeys(str(u).strip() for u in parsed if str(u).strip()))
                except Exception:
                    pass
            # 2. Extract full HTTP URLs without splitting on query parameter commas
            found_urls = re.findall(r"https?://[^\s\"']+", s)
            if found_urls:
                clean_urls = [u.rstrip(",;\"'") for u in found_urls if u.rstrip(",;\"'")]
                return list(dict.fromkeys(clean_urls))
            tokens = [u.strip().strip("'\"") for u in re.split(r"[\n;]+", s) if u.strip().strip("'\"")]
            return list(dict.fromkeys(tokens))
        if isinstance(v, (list, tuple, set)):
            return list(dict.fromkeys(str(u).strip() for u in v if str(u).strip()))
        return []

    @field_validator("agency_keywords", mode="before")
    @classmethod
    def parse_agency_keywords(cls, v: object) -> list[str]:
        if isinstance(v, str):
            s = v.strip()
            if (s.startswith("[") and s.endswith("]")) or (s.startswith("(") and s.endswith(")")):
                s = s[1:-1].strip()
            tokens = [k.strip().strip("'\"") for k in re.split(r"[,;\u060c\n]+", s) if k.strip().strip("'\"")]
            return list(dict.fromkeys(tokens))
        if isinstance(v, (list, tuple, set)):
            return list(dict.fromkeys(str(k).strip() for k in v if str(k).strip()))
        return ["املاک", "مشاور", "بنگاه", "مجتمع", "آژانس", "گروه", "شرکت"]

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        def _wrap_tolerant_decode(source: PydanticBaseSettingsSource) -> None:
            if hasattr(source, "decode_complex_value"):
                orig_decode: Any = source.decode_complex_value

                def _tolerant_decode(field_name: str, field: Any, value: Any) -> Any:
                    try:
                        return orig_decode(field_name, field, value)
                    except Exception:
                        return value

                object.__setattr__(source, "decode_complex_value", _tolerant_decode)

        _wrap_tolerant_decode(env_settings)
        _wrap_tolerant_decode(dotenv_settings)
        return init_settings, env_settings, dotenv_settings, file_secret_settings


_settings_instance: Settings | None = None


def get_settings() -> Settings:
    """Return cached Settings instance."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
