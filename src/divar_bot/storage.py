"""
SQLite storage layer using aiosqlite.
Tracks ad status, notifications, and cycle stats.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite

from divar_bot.models import Ad, AdStatus, CycleStats

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ads (
    token       TEXT PRIMARY KEY,
    status      TEXT NOT NULL DEFAULT 'seen',
    title       TEXT,
    url         TEXT,
    city        TEXT,
    district    TEXT,
    category    TEXT,
    created_at  TEXT,
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL,
    notified_at TEXT,
    raw_json    TEXT,
    reason      TEXT
);

CREATE TABLE IF NOT EXISTS notifications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    token       TEXT NOT NULL,
    chat_id     INTEGER NOT NULL,
    message_id  INTEGER,
    sent_at     TEXT NOT NULL,
    attempt     INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY(token) REFERENCES ads(token)
);

CREATE TABLE IF NOT EXISTS cycles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT NOT NULL,
    ended_at        TEXT,
    duration_sec    REAL,
    ads_seen        INTEGER DEFAULT 0,
    ads_new         INTEGER DEFAULT 0,
    ads_personal    INTEGER DEFAULT 0,
    ads_sent        INTEGER DEFAULT 0,
    ads_skipped_agency INTEGER DEFAULT 0,
    ads_failed      INTEGER DEFAULT 0,
    error           TEXT
);

CREATE INDEX IF NOT EXISTS idx_ads_status ON ads(status);
CREATE INDEX IF NOT EXISTS idx_ads_first_seen ON ads(first_seen);
CREATE INDEX IF NOT EXISTS idx_notifications_token ON notifications(token);
"""


class Storage:
    """Async SQLite storage for the bot."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    async def open(self) -> None:
        """Open connection and initialize schema."""
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._conn.executescript(_SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Ad tracking
    # ------------------------------------------------------------------

    async def is_known(self, token: str) -> bool:
        """Return True if token is already in the database."""
        async with self._lock:
            assert self._conn
            async with self._conn.execute(
                "SELECT 1 FROM ads WHERE token=?", (token,)
            ) as cur:
                return await cur.fetchone() is not None

    async def mark_seen(self, ad: Ad) -> None:
        """Insert ad as 'seen' if not already known."""
        now = _now_iso()
        async with self._lock:
            assert self._conn
            await self._conn.execute(
                """
                INSERT OR IGNORE INTO ads
                    (token, status, title, url, city, district, category,
                     created_at, first_seen, last_seen)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    ad.token,
                    AdStatus.SEEN.value,
                    ad.title,
                    ad.divar_url,
                    ad.city,
                    ad.district,
                    ad.category_slug,
                    ad.created_at.isoformat() if ad.created_at else None,
                    now,
                    now,
                ),
            )
            await self._conn.commit()

    async def mark_notified(self, token: str, msg_id: int | None = None) -> None:
        now = _now_iso()
        async with self._lock:
            assert self._conn
            await self._conn.execute(
                "UPDATE ads SET status=?, notified_at=? WHERE token=?",
                (AdStatus.NOTIFIED.value, now, token),
            )
            await self._conn.commit()

    async def mark_skipped_agency(self, token: str, reason: str) -> None:
        now = _now_iso()
        async with self._lock:
            assert self._conn
            await self._conn.execute(
                """
                INSERT INTO ads (token, status, reason, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(token) DO UPDATE SET
                    status=excluded.status,
                    reason=excluded.reason,
                    last_seen=excluded.last_seen
                """,
                (token, AdStatus.SKIPPED_AGENCY.value, reason, now, now),
            )
            await self._conn.commit()

    async def mark_failed(self, token: str, reason: str) -> None:
        now = _now_iso()
        async with self._lock:
            assert self._conn
            await self._conn.execute(
                """
                INSERT INTO ads (token, status, reason, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(token) DO UPDATE SET
                    status=excluded.status,
                    reason=excluded.reason,
                    last_seen=excluded.last_seen
                """,
                (token, AdStatus.FAILED.value, reason, now, now),
            )
            await self._conn.commit()

    async def get_status(self, token: str) -> AdStatus | None:
        async with self._lock:
            assert self._conn
            async with self._conn.execute(
                "SELECT status FROM ads WHERE token=?", (token,)
            ) as cur:
                row = await cur.fetchone()
                if row:
                    return AdStatus(row["status"])
                return None

    async def get_recent_notified(self, limit: int = 5) -> list[dict[str, Any]]:
        """Return recent notified ads for /last command."""
        async with self._lock:
            assert self._conn
            async with self._conn.execute(
                """
                SELECT token, title, url, district, notified_at
                FROM ads WHERE status='notified'
                ORDER BY notified_at DESC LIMIT ?
                """,
                (limit,),
            ) as cur:
                rows = await cur.fetchall()
                return [dict(r) for r in rows]

    async def count_by_status(self) -> dict[str, int]:
        """Count ads grouped by status."""
        async with self._lock:
            assert self._conn
            async with self._conn.execute(
                "SELECT status, COUNT(*) as cnt FROM ads GROUP BY status"
            ) as cur:
                rows = await cur.fetchall()
                return {r["status"]: r["cnt"] for r in rows}

    # ------------------------------------------------------------------
    # Cycle tracking
    # ------------------------------------------------------------------

    async def start_cycle(self) -> int:
        """Insert a new cycle record and return its ID."""
        now = _now_iso()
        async with self._lock:
            assert self._conn
            async with self._conn.execute(
                "INSERT INTO cycles (started_at) VALUES (?)", (now,)
            ) as cur:
                await self._conn.commit()
                return cur.lastrowid or 0

    async def end_cycle(self, stats: CycleStats) -> None:
        ended = _now_iso()
        async with self._lock:
            assert self._conn
            await self._conn.execute(
                """
                UPDATE cycles SET
                    ended_at=?, duration_sec=?,
                    ads_seen=?, ads_new=?, ads_personal=?,
                    ads_sent=?, ads_skipped_agency=?, ads_failed=?,
                    error=?
                WHERE id=?
                """,
                (
                    ended,
                    stats.duration_seconds,
                    stats.ads_seen,
                    stats.ads_new,
                    stats.ads_personal,
                    stats.ads_sent,
                    stats.ads_skipped_agency,
                    stats.ads_failed,
                    stats.error,
                    stats.cycle_id,
                ),
            )
            await self._conn.commit()

    async def get_last_cycle(self) -> dict[str, Any] | None:
        async with self._lock:
            assert self._conn
            async with self._conn.execute(
                "SELECT * FROM cycles ORDER BY id DESC LIMIT 1"
            ) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    async def get_cycle_count(self) -> int:
        async with self._lock:
            assert self._conn
            async with self._conn.execute("SELECT COUNT(*) FROM cycles") as cur:
                row = await cur.fetchone()
                return row[0] if row else 0


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()
