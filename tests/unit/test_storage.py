"""
Unit tests for Storage layer.
"""
from datetime import UTC, datetime

import pytest

from divar_bot.models import Ad, AdStatus, CycleStats
from divar_bot.storage import Storage


@pytest.fixture
async def storage(tmp_path):
    db_file = tmp_path / "test_storage.db"
    s = Storage(db_path=str(db_file))
    await s.open()
    yield s
    await s.close()


@pytest.mark.asyncio
async def test_storage_ad_lifecycle(storage):
    token = "test_ad_1"
    assert await storage.is_known(token) is False

    ad = Ad(token=token, title="عنوان تستی")
    await storage.mark_seen(ad)
    assert await storage.is_known(token) is True
    assert await storage.get_status(token) == AdStatus.SEEN

    await storage.mark_notified(token, msg_id=123)
    assert await storage.get_status(token) == AdStatus.NOTIFIED

    # Check recent notified
    recent = await storage.get_recent_notified(limit=5)
    assert len(recent) == 1
    assert recent[0]["token"] == token

    # Check counts
    counts = await storage.count_by_status()
    assert counts.get("notified") == 1


@pytest.mark.asyncio
async def test_storage_cycle_stats(storage):
    c_id = await storage.start_cycle()
    assert c_id > 0
    assert await storage.get_cycle_count() == 1

    stats = CycleStats(
        cycle_id=c_id,
        started_at=datetime.now(tz=UTC),
        ads_seen=10,
        ads_new=2,
        ads_personal=1,
        ads_sent=1,
        duration_seconds=1.5,
    )
    await storage.end_cycle(stats)

    last = await storage.get_last_cycle()
    assert last is not None
    assert last["id"] == c_id
    assert last["ads_seen"] == 10
    assert last["ads_sent"] == 1
