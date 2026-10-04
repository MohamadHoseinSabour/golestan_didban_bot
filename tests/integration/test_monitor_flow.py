"""
Integration tests for the monitor loop, state tracking, and notification flow.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from divar_bot.config import Settings
from divar_bot.divar.client import DivarClient, DivarNetworkError
from divar_bot.monitor import MonitorService
from divar_bot.storage import Storage
from divar_bot.telegram.bot import TelegramBot


@pytest.fixture
async def temp_storage(tmp_path):
    db_file = tmp_path / "test_monitor.db"
    storage = Storage(db_path=str(db_file))
    await storage.open()
    yield storage
    await storage.close()


@pytest.fixture
def mock_settings():
    return Settings(
        telegram_bot_token="test_token",
        allowed_user_ids=[12345],
        divar_urls=["https://divar.ir/s/ahvaz/real-estate/golestan"],
        poll_interval_seconds=60,
        jitter_seconds=1,
        max_ad_age_minutes=180,
        max_send_per_cycle=10,
        notify_on_first_run=0,
    )


@pytest.mark.asyncio
async def test_monitor_flow_new_ad_notified_once(temp_storage, mock_settings):
    """Verify new ad receives exactly 1 notification, and subsequent cycles send 0 notifications."""
    mock_divar = MagicMock(spec=DivarClient)
    # First cycle returns 1 widget
    mock_divar.fetch_listings = AsyncMock(return_value=[
        {"widget_type": "POST_ROW", "data": {"token": "token_abc123", "title": "آپارتمان شخصی"}}
    ])
    mock_divar.fetch_detail = AsyncMock(return_value={
        "webengage": {"business_type": "personal", "business_ref": "", "price": 5000000000},
        "seo": {"title": "آپارتمان شخصی در گلستان"},
        "sections": [
            {
                "section_name": "TITLE",
                "widgets": [{"widget_type": "TITLE_ROW", "data": {"title": "آپارتمان شخصی"}}]
            }
        ]
    })

    mock_bot = MagicMock(spec=TelegramBot)
    mock_bot.is_paused = False
    mock_bot.send_notification = AsyncMock(return_value=[999])
    mock_bot.send_health_alert = AsyncMock()

    monitor = MonitorService(
        settings=mock_settings,
        storage=temp_storage,
        divar_client=mock_divar,
        telegram_bot=mock_bot,
    )

    # 1. Baseline initialization (first cycle)
    stats1 = await monitor.run_cycle()
    assert stats1.ads_seen == 1
    # On first run with notify_on_first_run=0, ads are marked seen without sending
    assert stats1.ads_sent == 0
    assert await temp_storage.is_known("token_abc123") is True

    # 2. Add a truly new ad for cycle 2
    mock_divar.fetch_listings = AsyncMock(return_value=[
        {"widget_type": "POST_ROW", "data": {"token": "token_abc123", "title": "آپارتمان قدیمی"}},
        {"widget_type": "POST_ROW", "data": {"token": "token_new999", "title": "آپارتمان جدید"}},
    ])
    mock_divar.fetch_detail = AsyncMock(return_value={
        "webengage": {"business_type": "personal", "business_ref": "", "price": 4000000000},
        "seo": {"title": "آپارتمان جدید در گلستان"},
        "sections": []
    })

    stats2 = await monitor.run_cycle()
    assert stats2.ads_new == 1
    assert stats2.ads_personal == 1
    assert stats2.ads_sent == 1
    assert mock_bot.send_notification.call_count == 1

    # 3. Cycle 3: Same ads -> 0 notifications sent (deduplication verified!)
    stats3 = await monitor.run_cycle()
    assert stats3.ads_new == 0
    assert stats3.ads_sent == 0
    assert mock_bot.send_notification.call_count == 1  # Still 1, no duplicate


@pytest.mark.asyncio
async def test_monitor_skips_agency_ad(temp_storage, mock_settings):
    """Verify that ads classified as agency are skipped and recorded with reason."""
    mock_divar = MagicMock(spec=DivarClient)
    mock_divar.fetch_listings = AsyncMock(return_value=[
        {"widget_type": "POST_ROW", "data": {"token": "agency_token_1", "title": "دفتر املاک"}}
    ])
    mock_divar.fetch_detail = AsyncMock(return_value={
        "webengage": {"business_type": "premium-panel", "business_ref": "agency_999"},
        "seo": {"title": "فروش واحد توسط دفتر املاک"},
        "sections": []
    })

    mock_bot = MagicMock(spec=TelegramBot)
    mock_bot.is_paused = False
    mock_bot.send_notification = AsyncMock()

    monitor = MonitorService(
        settings=mock_settings,
        storage=temp_storage,
        divar_client=mock_divar,
        telegram_bot=mock_bot,
    )
    monitor._is_first_run = False  # Set to normal mode

    stats = await monitor.run_cycle()
    assert stats.ads_new == 1
    assert stats.ads_skipped_agency == 1
    assert stats.ads_sent == 0
    mock_bot.send_notification.assert_not_called()

    # Check reason in DB
    status = await temp_storage.get_status("agency_token_1")
    assert status.value == "skipped_agency"


@pytest.mark.asyncio
async def test_circuit_breaker_health_alert(temp_storage, mock_settings):
    """Verify that after 3 consecutive failures, a single health alert is dispatched."""
    mock_divar = MagicMock(spec=DivarClient)
    mock_divar.fetch_listings = AsyncMock(side_effect=DivarNetworkError("Network down"))

    mock_bot = MagicMock(spec=TelegramBot)
    mock_bot.is_paused = False
    mock_bot.send_health_alert = AsyncMock()

    monitor = MonitorService(
        settings=mock_settings,
        storage=temp_storage,
        divar_client=mock_divar,
        telegram_bot=mock_bot,
    )

    # Fail cycle 1
    await monitor.run_cycle()
    assert mock_bot.send_health_alert.call_count == 0

    # Fail cycle 2
    await monitor.run_cycle()
    assert mock_bot.send_health_alert.call_count == 0

    # Fail cycle 3 -> trigger health alert!
    await monitor.run_cycle()
    assert mock_bot.send_health_alert.call_count == 1

    # Fail cycle 4 -> no duplicate alert (spam prevention!)
    await monitor.run_cycle()
    assert mock_bot.send_health_alert.call_count == 1

    # Cycle 5 recovers!
    mock_divar.fetch_listings = AsyncMock(return_value=[])
    await monitor.run_cycle()
    # Recovery alert sent!
    assert mock_bot.send_health_alert.call_count == 2
