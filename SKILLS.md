# Skills & Tools Selection (Phase 1)

| Need | Selected Tool / Library | Source / Version | Justification | Alternatives Considered |
|---|---|---|---|---|
| **Python & Packaging** | Python 3.12, PEP 517 (`pyproject.toml` with `hatchling`) | Official Python standard | Clean metadata, modern standards, dependency separation | `setup.py`, `poetry` |
| **Telegram Bot** | `python-telegram-bot` (v21+) | PyPI (`>=21.0`) | Full async/await, native SOCKS5/HTTP proxy support (`httpx` backend), custom base URL (`base_url` parameter) for reverse proxies, robust error handling (`RetryAfter`, `NetworkError`) | `aiogram 3` (ptb v21 is more stable with proxy setup and has built-in `ApplicationBuilder`) |
| **HTTP Client & Scraping** | `httpx` (async, HTTP/2, socks) + `tenacity` | PyPI | Fast async requests, connection pooling, proxy support, custom headers, tenacity for jittered backoff | `aiohttp`, `requests` |
| **HTML / Browser Automation** | `selectolax` + `playwright` (Chromium) | PyPI | `selectolax` for ultra-fast HTML parsing when needed. `playwright` as headless fallback if API is blocked. | `BeautifulSoup4`, `Selenium` |
| **Data Validation & Config** | `pydantic` v2 + `pydantic-settings` + `pyyaml` | PyPI | Strict typing, `.env` loading, nested `config.yaml` support, runtime validation | `dynaconf`, plain `dict` |
| **Database** | `aiosqlite` (SQLite with WAL mode) | PyPI | Embedded, zero-maintenance, zero-daemon, async, WAL mode allows concurrent reads without locking | `PostgreSQL`, `MongoDB` |
| **Timezone & Persian formatting** | `pytz` ("Asia/Tehran") + custom Persian utils | Built-in / PyPI | Strict timezone awareness, Arabic normalization, Persian digits and thousand separator formatting | `jdatetime`, `arrow` |
| **Testing & Quality** | `pytest`, `pytest-asyncio`, `respx`, `pytest-cov`, `ruff`, `mypy` | PyPI | Fast linting with Ruff, static type checking with Mypy strict mode, async mock testing with respx | `flake8`, `black`, `unittest` |
| **Deployment** | Docker multi-stage build, `docker-compose.yml`, systemd service | Docker / Linux | Self-contained, portable for local Docker, systemd on VPS, and Railway PaaS | Manual `nohup` |
