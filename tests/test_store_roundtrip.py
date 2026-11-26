"""Integration tests: sync writes → queries read back."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from fitness_mcp.store import queries, sync


@pytest.mark.asyncio
async def test_sync_activities_populates_and_dedupes(tmp_db, fake_provider):
    start = date.today() - timedelta(days=4)
    end = date.today() - timedelta(days=2)

    r1 = await sync.sync_activities(fake_provider, start, end)
    assert r1.stale_days == 3
    assert r1.fetched_records == 3
    assert len(fake_provider.activity_calls) == 1

    # Second call: nothing stale anymore.
    r2 = await sync.sync_activities(fake_provider, start, end)
    assert r2.stale_days == 0
    assert r2.fetched_records == 0
    assert len(fake_provider.activity_calls) == 1

    # force_refresh re-fetches everything.
    r3 = await sync.sync_activities(fake_provider, start, end, force=True)
    assert r3.stale_days == 3
    assert len(fake_provider.activity_calls) == 2

    rows = queries.list_activities(start, end)
    assert len(rows) == 3
    assert {r["sport"] for r in rows} == {"running"}


@pytest.mark.asyncio
async def test_sport_filter(tmp_db, fake_provider):
    start = date.today() - timedelta(days=10)
    end = date.today() - timedelta(days=8)
    await sync.sync_activities(fake_provider, start, end)
    assert queries.list_activities(start, end, sport="running")
    assert queries.list_activities(start, end, sport="cycling") == []


@pytest.mark.asyncio
async def test_sleep_and_daily_summary(tmp_db, fake_provider):
    start = date.today() - timedelta(days=5)
    end = date.today() - timedelta(days=3)
    await sync.sync_wellness(fake_provider, start, end)
    await sync.sync_sleep(fake_provider, start, end)

    rows = queries.daily_summary(start, end)
    assert len(rows) == 3
    for r in rows:
        assert r["sleep_hours"] == 7.5
        assert r["sleep_score"] == 80
        assert r["steps"] == 8000


@pytest.mark.asyncio
async def test_trends_week_bucketing(tmp_db, fake_provider):
    # 14 days ending 4 days ago so nothing falls in the "today" window.
    end = date.today() - timedelta(days=4)
    start = end - timedelta(days=13)
    await sync.sync_wellness(fake_provider, start, end)

    series = queries.trend("steps", start, end, bucket="week")
    assert series, "expected at least one weekly bucket"
    for b in series:
        # Weekly sum: 7 days * 8000 steps when the bucket is whole.
        assert b["value"] >= 8000
        assert b["n"] >= 1


@pytest.mark.asyncio
async def test_trends_unknown_metric_falls_back_to_metrics_table(tmp_db, fake_provider):
    start = date.today() - timedelta(days=4)
    end = date.today() - timedelta(days=2)
    await sync.sync_metrics(fake_provider, start, end)
    series = queries.trend("vo2max", start, end, bucket="day")
    assert len(series) == 3
    assert all(round(b["value"], 2) == 52.00 for b in series)
