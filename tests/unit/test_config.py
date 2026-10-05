"""
Unit tests for configuration loading and validation (Settings).
Tests env var parsing for ALLOWED_USER_IDS, DIVAR_URLS, etc.
"""
from __future__ import annotations

import pytest

from divar_bot.config import Settings, get_settings


def test_allowed_user_ids_single_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_USER_IDS", "123456789")
    settings = Settings()
    assert settings.allowed_user_ids == [123456789]


def test_allowed_user_ids_multiple_comma_separated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_USER_IDS", "123456789,987654321")
    settings = Settings()
    assert settings.allowed_user_ids == [123456789, 987654321]


def test_allowed_user_ids_with_spaces_and_trailing_comma(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_USER_IDS", "  123456789 ,  987654321 , ")
    settings = Settings()
    assert settings.allowed_user_ids == [123456789, 987654321]


def test_allowed_user_ids_json_format(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_USER_IDS", "[123456789, 987654321]")
    settings = Settings()
    assert settings.allowed_user_ids == [123456789, 987654321]


def test_allowed_user_ids_persian_digits_and_comma(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_USER_IDS", "۱۲۳۴۵۶۷۸۹، ۹۸۷۶۵۴۳۲۱")
    settings = Settings()
    assert settings.allowed_user_ids == [123456789, 987654321]


def test_allowed_user_ids_negative_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_USER_IDS", "-100123456789, 987654321")
    settings = Settings()
    assert settings.allowed_user_ids == [-100123456789, 987654321]


def test_allowed_user_ids_space_and_semicolon(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_USER_IDS", "123456789; 987654321 55555")
    settings = Settings()
    assert settings.allowed_user_ids == [123456789, 987654321, 55555]


def test_allowed_user_ids_deduplication(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_USER_IDS", "123456789, 123456789, 987654321")
    settings = Settings()
    assert settings.allowed_user_ids == [123456789, 987654321]


def test_allowed_user_ids_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_USER_IDS", "")
    settings = Settings()
    assert settings.allowed_user_ids == []


def test_allowed_user_ids_direct_args() -> None:
    assert Settings(allowed_user_ids=12345).allowed_user_ids == [12345]
    assert Settings(allowed_user_ids=[123, 456]).allowed_user_ids == [123, 456]
    assert Settings(allowed_user_ids=["۱۲۳", "۴۵۶"]).allowed_user_ids == [123, 456]


def test_divar_urls_comma_separated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DIVAR_URLS",
        "https://divar.ir/s/tehran/buy-apartment, https://divar.ir/s/ahvaz/buy-apartment",
    )
    settings = Settings()
    assert settings.divar_urls == [
        "https://divar.ir/s/tehran/buy-apartment",
        "https://divar.ir/s/ahvaz/buy-apartment",
    ]


def test_agency_keywords_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENCY_KEYWORDS", "املاک, بنگاه, دفتر")
    settings = Settings()
    assert settings.agency_keywords == ["املاک", "بنگاه", "دفتر"]


def test_get_settings_caching() -> None:
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_allowed_user_ids_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALLOWED_USER_IDS", raising=False)
    monkeypatch.setenv("ALLOWED_USER_ID", "275352822, 1069082757")
    settings = Settings()
    assert settings.allowed_user_ids == [275352822, 1069082757]

