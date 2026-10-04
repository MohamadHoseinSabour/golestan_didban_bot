# Stack Decision & Architecture Rationale (Phase 1)

## 1. Programming Language & Runtime
- **Python 3.12**: Native async improvements, improved exception groups, performance improvements.
- **Packaging**: `pyproject.toml` using `hatchling` (PEP 517 / PEP 621 compliant).

## 2. Telegram Bot Framework: `python-telegram-bot` (v21+)
### Rationale:
- **Proxy Compatibility**: `python-telegram-bot` uses `httpx` under the hood. Supporting `socks5://` or `http://` proxies for Iranian networking constraints is completely native through `HTTPXRequest(proxy_url=...)`.
- **Custom Base URL**: Allows configuring reverse proxies via `base_url` parameter if Telegram API is reverse-proxied.
- **Robust Long-Polling**: Excellent connection recovery, built-in rate limit handling with `RetryAfter`.
- **Alternative considered**: `aiogram 3`. While modern, `python-telegram-bot` has cleaner proxy integration and simpler thread/task lifecycle management for background cron-like monitoring loops.

## 3. Web Scraping & HTTP Engine: `httpx` + `tenacity`
### Rationale:
- **Direct Protobuf-over-JSON API**: Discovered during Phase 2 recon. Divar web client calls `POST https://api.divar.ir/v8/postlist/w/search` and `GET https://api.divar.ir/v8/posts-v2/web/<token>`.
- **Polite & Async**: Only 1 list request per minute (~60s), and detail requests only for genuinely new tokens.
- **Resilience**: `tenacity` provides exponential backoff with jitter on 429/5xx status codes.
- **Fallback**: `playwright` (Chromium) is configured as a fallback engine if Divar applies challenge pages or alters the API.

## 4. Database: Embedded `SQLite` with `aiosqlite`
### Rationale:
- **No external server**: Zero memory footprint overhead, zero ops burden for local runs or lightweight Railway containers.
- **WAL Mode (Write-Ahead Logging)**: Enables concurrent reads while writing.
- **State safety**: Each ad has a state machine: `seen -> notified | skipped_agency | skipped_old | failed`.
- **Restart safety**: SQLite file persists across bot restarts without losing seen tokens.

## 5. Persian Typography & Time Handling
- Timezone is strictly locked to `Asia/Tehran` via `pytz`.
- Number rendering uses custom `to_persian_digits` with Persian thousand separators (`٬`).
- Missing fields in listings evaluate to `None` and are cleanly excluded from output formatting (never placeholder "نامشخص" text).
