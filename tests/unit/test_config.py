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


def test_allowed_user_ids_bracket_compact(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_USER_IDS", "[1,2,3]")
    settings = Settings()
    assert settings.allowed_user_ids == [1, 2, 3]


def test_allowed_user_ids_quoted_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_USER_IDS", '"[1, 2, 3]"')
    settings = Settings()
    assert settings.allowed_user_ids == [1, 2, 3]


def test_allowed_user_ids_single_quoted_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_USER_IDS", "'[1,2,3]'")
    settings = Settings()
    assert settings.allowed_user_ids == [1, 2, 3]


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


def test_divar_url_singular_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DIVAR_URLS", raising=False)
    monkeypatch.setenv("DIVAR_URL", "https://divar.ir/s/ahvaz/buy-apartment/golestan")
    settings = Settings()
    assert settings.divar_urls == ["https://divar.ir/s/ahvaz/buy-apartment/golestan"]


def test_divar_search_url_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DIVAR_URLS", raising=False)
    monkeypatch.delenv("DIVAR_URL", raising=False)
    monkeypatch.setenv("DIVAR_SEARCH_URL", "https://divar.ir/s/ahvaz/rent-residential/golestan")
    settings = Settings()
    assert settings.divar_urls == ["https://divar.ir/s/ahvaz/rent-residential/golestan"]


def test_divar_urls_with_query_param_commas(monkeypatch: pytest.MonkeyPatch) -> None:
    u1 = "https://divar.ir/s/ahvaz/buy-apartment/golestan?bbox=48.625,31.261&business-type=personal,&districts=4574,"
    u2 = "https://divar.ir/s/ahvaz/rent-residential/golestan?bbox=48.621,31.240&business-type=personal,"
    monkeypatch.setenv("DIVAR_URLS", f"{u1}, {u2}")
    settings = Settings()
    assert len(settings.divar_urls) == 2
    assert "buy-apartment" in settings.divar_urls[0]
    assert "rent-residential" in settings.divar_urls[1]


def test_divar_urls_json_array_env(monkeypatch: pytest.MonkeyPatch) -> None:
    u1 = "https://divar.ir/s/ahvaz/buy-apartment/golestan?business-type=personal,"
    u2 = "https://divar.ir/s/ahvaz/rent-residential/golestan?business-type=personal,"
    monkeypatch.setenv("DIVAR_URLS", f'["{u1}", "{u2}"]')
    settings = Settings()
    assert settings.divar_urls == [u1, u2]


def test_enable_agency_filter_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_AGENCY_FILTER", "false")
    settings = Settings()
    assert settings.enable_agency_filter is False

    monkeypatch.setenv("ENABLE_AGENCY_FILTER", "true")
    settings = Settings()
    assert settings.enable_agency_filter is True

    monkeypatch.delenv("ENABLE_AGENCY_FILTER", raising=False)
    monkeypatch.setenv("FILTER_AGENCY", "0")
    settings = Settings()
    assert settings.enable_agency_filter is False


