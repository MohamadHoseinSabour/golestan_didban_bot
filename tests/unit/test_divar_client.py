"""
Unit tests for DivarClient error handling and retries with respx.
"""
import httpx
import pytest
import respx

from divar_bot.divar.client import (
    DivarBlockedError,
    DivarClient,
    DivarRateLimitError,
    DivarSchemaError,
)
from divar_bot.divar.url_builder import DivarSearchParams


@pytest.mark.asyncio
@respx.mock
async def test_divar_client_fetch_listings_success():
    respx.post("https://api.divar.ir/v8/postlist/w/search").mock(
        return_value=httpx.Response(
            200,
            json={"list_widgets": [{"widget_type": "POST_ROW", "data": {"token": "t1"}}]}
        )
    )

    async with DivarClient() as client:
        params = DivarSearchParams(city_slug="ahvaz", category_slug="real-estate")
        widgets = await client.fetch_listings(params)
        assert len(widgets) == 1
        assert widgets[0]["data"]["token"] == "t1"
        assert client.consecutive_failures == 0


@pytest.mark.asyncio
@respx.mock
async def test_divar_client_rate_limited():
    respx.post("https://api.divar.ir/v8/postlist/w/search").mock(
        return_value=httpx.Response(429, text="Too Many Requests")
    )

    async with DivarClient() as client:
        params = DivarSearchParams(city_slug="ahvaz", category_slug="real-estate")
        with pytest.raises(DivarRateLimitError):
            await client.fetch_listings(params)
        assert client.consecutive_failures == 1


@pytest.mark.asyncio
@respx.mock
async def test_divar_client_blocked():
    respx.post("https://api.divar.ir/v8/postlist/w/search").mock(
        return_value=httpx.Response(403, text="Forbidden")
    )

    async with DivarClient() as client:
        params = DivarSearchParams(city_slug="ahvaz", category_slug="real-estate")
        with pytest.raises(DivarBlockedError):
            await client.fetch_listings(params)
        assert client.consecutive_failures == 1


@pytest.mark.asyncio
@respx.mock
async def test_divar_client_schema_error():
    respx.post("https://api.divar.ir/v8/postlist/w/search").mock(
        return_value=httpx.Response(200, text="Not a JSON")
    )

    async with DivarClient() as client:
        params = DivarSearchParams(city_slug="ahvaz", category_slug="real-estate")
        with pytest.raises(DivarSchemaError):
            await client.fetch_listings(params)


@pytest.mark.asyncio
@respx.mock
async def test_divar_client_detail_success():
    respx.get("https://api.divar.ir/v8/posts-v2/web/token123").mock(
        return_value=httpx.Response(200, json={"token": "token123", "sections": []})
    )

    async with DivarClient() as client:
        detail = await client.fetch_detail("token123")
        assert detail["token"] == "token123"


@pytest.mark.asyncio
@respx.mock
async def test_divar_client_fetch_contact():
    # Without auth token
    async with DivarClient() as client:
        assert client.has_auth_token is False
        assert await client.fetch_contact("token123") is None

    # With auth token - success
    respx.get("https://api.divar.ir/v8/postcontact/web/contact_info/token123").mock(
        return_value=httpx.Response(200, json={"phone": "09161234567"})
    )
    async with DivarClient(auth_token="my_token") as client:
        assert client.has_auth_token is True
        contact = await client.fetch_contact("token123")
        assert contact == {"phone": "09161234567"}

    # With auth token - 403 error handled gracefully
    respx.get("https://api.divar.ir/v8/postcontact/web/contact_info/token456").mock(
        return_value=httpx.Response(403, text="Forbidden")
    )
    async with DivarClient(auth_token="my_token") as client:
        contact = await client.fetch_contact("token456")
        assert contact is None
