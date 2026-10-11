# PROGRESS.md — Golestan Didban Bot

> **Single source of truth** for project state, decisions, and metrics.

---

## Project Metadata

| Key | Value |
|-----|-------|
| Start time (UTC) | 2026-10-04T22:10:00Z |
| Python version | 3.12.10 |
| Deployment targets | Local Windows laptop (dev) → Railway (prod) |
| DIVAR_URLS | Buy Apartment & Residential Rent in Golestan Ahvaz |
| ALLOWED_USER_IDS | Set by user in .env (multi-user support) |
| TELEGRAM_BOT_TOKEN | Set by user in .env |
| Proxies needed | Unknown until recon; Railway is outside Iran so Divar proxy may be needed |

---

## Phase Checklist

- [x] **Phase 0** — Setup & measurement (2026-10-04T22:10Z)
- [x] **Phase 1** — Stack selection & skills (2026-10-04T22:25Z)
- [x] **Phase 2** — Real recon on Divar (2026-10-04T22:45Z)
- [x] **Phase 3** — Architecture & skeleton (2026-10-04T22:55Z)
- [x] **Phase 4** — Divar client & scraper (2026-10-04T23:10Z)
- [x] **Phase 5** — Parser, normalizer, classifier (2026-10-04T23:25Z)
- [x] **Phase 6** — Telegram: notifications, security, commands (2026-10-04T23:35Z)
- [x] **Phase 7** — Monitor loop & resilience (2026-10-04T23:45Z)
- [x] **Phase 8** — Full testing with real data (2026-10-04T23:55Z)
- [x] **Phase 9** — Packaging, docs, delivery (2026-10-05T00:05Z)
- [x] **Phase 10** — Multi-URL monitoring: Buy Apartment + Residential Rent (2026-10-11)
- [x] **Phase 11** — Fix Rent/Mortgage priority, disclaimer masking, and district boundary bbox clipping (2026-10-11)

---

## Final Project Metrics
- **Tests:** 60/60 passed (100%)
- **Static Analysis:**
  - `ruff check`: 0 errors
  - `mypy src`: 0 errors (strict mode across 20 source files)
- **Live Recon:** Real Protobuf-over-JSON endpoints confirmed (`/v8/postlist/w/search` and `/v8/posts-v2/web/:token`)
- **Classifier:** 2-layer detection (Divar official `business_type`/`business_ref` + keyword heuristic with landlord disclaimer masking)
- **Deployment Artifacts:** Dockerfile, docker-compose.yml, railway.json, divar_bot.service
- **Documentation:** Complete Persian README.md, divar_recon.md, stack_decision.md, architecture.md

---

## Phase 0 — Setup
**Status:** ✅ Done (2026-10-04T22:10Z)

## Phase 1 — Stack Selection
**Status:** ✅ Done (2026-10-04T22:25Z)
See `SKILLS.md` and `docs/stack_decision.md`.

## Phase 2 — Divar Recon
**Status:** ✅ Done (2026-10-04T22:45Z)
See `docs/divar_recon.md` and `docs/reviews/phase_2.md`.
Verified:
- Search API: `POST https://api.divar.ir/v8/postlist/w/search` (200 OK)
- Detail API: `GET https://api.divar.ir/v8/posts-v2/web/<token>` (200 OK)
- `bbox` parameter actively narrows listings to user viewport.
- `business-type: personal` confirmed 100% accurate on sample; 2nd layer defense via `webengage` + keywords.

### Decisions Log
| Decision | Choice | Reason | Alternative |
|----------|--------|--------|-------------|
| Telegram library | python-telegram-bot v21 | Async, proxy support, well-maintained | aiogram 3 |
| HTTP client | httpx (async) | HTTP/2, timeout control, proxy, retries via tenacity | aiohttp |
| HTML parser | selectolax | Fast, lightweight | bs4 |
| Browser automation | Playwright (fallback only) | Chromium, network intercept | selenium |
| Database | aiosqlite | Async SQLite, no extra server | redis |
| Config | pydantic-settings + config.yaml | Type-safe, env override | dynaconf |
| Linting | ruff + mypy | Fast, modern | pylint + pyright |
| Testing | pytest + pytest-asyncio + respx | Async support, HTTP mocking | unittest |
| Packaging | pyproject.toml (hatchling) | Modern PEP 517 | setup.py |

---

## Phase 2 — Divar Recon

**Status:** ⏳ Pending

### Hypotheses to verify
- [ ] API endpoint: `POST https://api.divar.ir/v8/postlist/w/search`
- [ ] Detail endpoint: `GET https://api.divar.ir/v8/posts-v2/web/<token>`
- [ ] `business-type=personal` effectively filters agencies
- [ ] `bbox` provides additional geographic filtering beyond neighborhood slug
- [ ] Sort by newest is possible via API parameter

---

## Phase 3 — Architecture

**Status:** ⏳ Pending

---

## Phase 4 — Divar Client

**Status:** ⏳ Pending

---

## Phase 5 — Parser & Classifier

**Status:** ⏳ Pending

---

## Phase 6 — Telegram Bot

**Status:** ⏳ Pending

---

## Phase 7 — Monitor Loop

**Status:** ⏳ Pending

---

## Phase 8 — Full Testing

**Status:** ⏳ Pending

---

## Phase 9 — Packaging & Delivery

**Status:** ⏳ Pending

---

## Open Problems

_(none yet)_

---

## Metrics

| Phase | Start (UTC) | End (UTC) | Duration | Token estimate |
|-------|-------------|-----------|----------|----------------|
| 0 | 2026-10-04T22:10Z | TBD | TBD | ~5k (est.) |
| 1 | TBD | TBD | TBD | TBD |
| 2 | TBD | TBD | TBD | TBD |
