"""
HTTP client for Divar API.
Handles listing queries, detail queries, rate-limits, retries, and proxies.
"""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from divar_bot.divar.url_builder import DivarSearchParams
from divar_bot.utils.logging import get_logger

logger = get_logger(__name__)

API_BASE_URL = "https://api.divar.ir"
SEARCH_ENDPOINT = f"{API_BASE_URL}/v8/postlist/w/search"
DETAIL_ENDPOINT_TEMPLATE = f"{API_BASE_URL}/v8/posts-v2/web/{{token}}"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fa,en;q=0.9",
    "Content-Type": "application/json",
    "Origin": "https://divar.ir",
    "Referer": "https://divar.ir/",
    "x-web-serving-mode": "desktop",
}


class DivarClientError(Exception):
    """Base exception for Divar client."""


class DivarRateLimitError(DivarClientError):
    """Raised on 429 Too Many Requests."""


class DivarBlockedError(DivarClientError):
    """Raised on 403 Forbidden or captcha challenge."""


class DivarNetworkError(DivarClientError):
    """Raised on connection timeout or network disconnect."""


class DivarSchemaError(DivarClientError):
    """Raised when Divar response schema is invalid or unexpected."""


class DivarClient:
    """Async HTTP client for querying Divar listing and detail APIs."""

    def __init__(
        self,
        proxy_url: str | None = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        self._proxy_url = proxy_url
        self._timeout_seconds = timeout_seconds
        self._client: httpx.AsyncClient | None = None
        self._consecutive_failures = 0

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    async def __aenter__(self) -> DivarClient:
        await self.open()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def open(self) -> None:
        if self._client is None:
            transport_kwargs: dict[str, Any] = {}
            if self._proxy_url:
                transport_kwargs["proxy"] = self._proxy_url
                logger.info("divar_client_using_proxy", proxy=self._proxy_url)

            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout_seconds, connect=10.0),
                headers=DEFAULT_HEADERS,
                follow_redirects=True,
                **transport_kwargs,
            )

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("DivarClient is not open. Call open() or use async context.")
        return self._client

    @retry(
        retry=retry_if_exception_type(DivarNetworkError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def fetch_listings(self, params: DivarSearchParams) -> list[dict[str, Any]]:
        """
        Fetch the current search listings.
        Returns a list of raw widget dictionaries representing POST_ROW ads.
        """
        client = self._ensure_client()
        payload = params.to_api_payload()

        try:
            response = await client.post(SEARCH_ENDPOINT, json=payload)
        except (httpx.TimeoutException, httpx.NetworkError) as err:
            self._consecutive_failures += 1
            logger.error("divar_search_network_error", error=str(err))
            raise DivarNetworkError(f"Network error querying Divar: {err}") from err

        if response.status_code == 429:
            self._consecutive_failures += 1
            logger.warning("divar_rate_limited", status=429)
            raise DivarRateLimitError("Divar rate limited (HTTP 429)")

        if response.status_code in (401, 403):
            self._consecutive_failures += 1
            logger.error("divar_blocked", status=response.status_code)
            raise DivarBlockedError(f"Divar access blocked (HTTP {response.status_code})")

        if response.status_code >= 400:
            self._consecutive_failures += 1
            logger.error("divar_http_error", status=response.status_code, body=response.text[:200])
            raise DivarClientError(f"HTTP {response.status_code}: {response.text[:100]}")

        try:
            data = response.json()
        except Exception as err:
            self._consecutive_failures += 1
            logger.error("divar_invalid_json", error=str(err))
            raise DivarSchemaError("Invalid JSON from Divar search") from err

        widgets = data.get("list_widgets", [])
        if not isinstance(widgets, list):
            self._consecutive_failures += 1
            raise DivarSchemaError("list_widgets is missing or not a list")

        # Success resets consecutive failure counter
        self._consecutive_failures = 0
        post_widgets = [
            w for w in widgets
            if isinstance(w, dict) and w.get("widget_type") == "POST_ROW"
        ]
        logger.info(
            "divar_search_fetched",
            total_widgets=len(widgets),
            post_widgets=len(post_widgets),
        )
        return post_widgets

    @retry(
        retry=retry_if_exception_type(DivarNetworkError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        reraise=True,
    )
    async def fetch_detail(self, token: str) -> dict[str, Any]:
        """
        Fetch full ad details by token.
        """
        client = self._ensure_client()
        url = DETAIL_ENDPOINT_TEMPLATE.format(token=token)

        try:
            response = await client.get(url)
        except (httpx.TimeoutException, httpx.NetworkError) as err:
            logger.error("divar_detail_network_error", token=token, error=str(err))
            raise DivarNetworkError(f"Network error querying detail for {token}: {err}") from err

        if response.status_code == 429:
            raise DivarRateLimitError(f"Divar rate limited on token {token}")

        if response.status_code in (401, 403):
            raise DivarBlockedError(f"Divar blocked on token {token}")

        if response.status_code == 404:
            raise DivarClientError(f"Post {token} not found (HTTP 404)")

        if response.status_code >= 400:
            raise DivarClientError(f"HTTP {response.status_code} on token {token}")

        try:
            return response.json()  # type: ignore[no-any-return]
        except Exception as err:
            raise DivarSchemaError(f"Invalid JSON for token {token}") from err
