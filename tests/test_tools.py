"""Smoke tests for the public tool entrypoints."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from fitness_mcp.tools import activities, sleep, trends, wellness


def _days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


@pytest.mark.asyncio
async def test_get_activities_happy_path(tmp_db, fake_provider):
    out = await activities.list_activities(_days_ago(3), _days_ago(1), sport=None, force_refresh=False)
    assert "activities" in out and len(out["activities"]) == 3
    assert out["source"] == "garmin"
    assert out["range"]["clamped"] is False
    assert out["stale_days_resynced"] == 3


@pytest.mark.asyncio
async def test_get_activities_bad_date_returns_error_payload(tmp_db, fake_provider):
    out = await activities.list_activities("not-a-date", _days_ago(0), None, False)
    assert "error" in out
    assert out["error"]["type"] == "ValidationError"


@pytest.mark.asyncio
async def test_get_activities_start_after_end(tmp_db, fake_provider):
    out = await activities.list_activities(_days_ago(0), _days_ago(5), None, False)
    assert out.get("error", {}).get("type") == "ValidationError"


@pytest.mark.asyncio
async def test_get_sleep(tmp_db, fake_provider):
    out = await sleep.list_sleep(_days_ago(3), _days_ago(1), force_refresh=False)
    assert len(out["sleep"]) == 3


@pytest.mark.asyncio
async def test_daily_summary(tmp_db, fake_provider):
    out = await wellness.daily_summary(_days_ago(3), _days_ago(1), force_refresh=False)
    assert len(out["days"]) == 3
    assert out["fetched_from_provider"]["sleep"] == 3
    assert out["fetched_from_provider"]["wellness"] == 3


@pytest.mark.asyncio
async def test_trend_steps(tmp_db, fake_provider):
    out = await trends.trend("steps", _days_ago(7), _days_ago(1), "day")
    assert out["metric"] == "steps"
    assert len(out["series"]) == 7


@pytest.mark.asyncio
async def test_trend_bad_bucket(tmp_db, fake_provider):
    out = await trends.trend("steps", _days_ago(7), _days_ago(1), "decade")
    assert out["error"]["type"] == "ValidationError"
