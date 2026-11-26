"""Shared test fixtures.

All tests run against an isolated SQLite file in a tmp dir, with a FakeProvider
wired into the registry — no network calls, no real Garmin credentials.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta

import pytest

from fitness_mcp import config
from fitness_mcp.models import Activity, DailyWellness, MetricPoint, SleepNight
from fitness_mcp.providers.base import Provider
from fitness_mcp.providers.registry import default_registry
from fitness_mcp.store import db as db_module


class FakeProvider(Provider):
    name = "garmin"

    def __init__(self) -> None:
        self.activity_calls: list[tuple[date, date]] = []
        self.sleep_calls: list[tuple[date, date]] = []
        self.wellness_calls: list[tuple[date, date]] = []
        self.metric_calls: list[tuple[date, date]] = []

    async def fetch_activities(self, start: date, end: date) -> Sequence[Activity]:
        self.activity_calls.append((start, end))
        out: list[Activity] = []
        cur = start
        while cur <= end:
            out.append(Activity(
                source=self.name,
                id=f"act-{cur.isoformat()}",
                day=cur,
                sport="running",
                name=f"Run on {cur}",
                start=datetime.combine(cur, datetime.min.time()),
                km=10.0,
                minutes=55.0,
                avg_hr=150,
                max_hr=175,
                elevation_m=50.0,
                training_load=120.0,
                raw={"stub": True},
            ))
            cur += timedelta(days=1)
        return out

    async def fetch_activity_detail(self, activity_id: str) -> dict:
        return {"activityId": activity_id, "stub": True}

    async def fetch_sleep(self, start: date, end: date) -> Sequence[SleepNight]:
        self.sleep_calls.append((start, end))
        out: list[SleepNight] = []
        cur = start
        while cur <= end:
            out.append(SleepNight(
                source=self.name, day=cur, hours=7.5,
                deep_min=90, rem_min=90, light_min=270, awake_min=10,
                score=80, raw={"stub": True},
            ))
            cur += timedelta(days=1)
        return out

    async def fetch_daily_wellness(self, start: date, end: date) -> Sequence[DailyWellness]:
        self.wellness_calls.append((start, end))
        out: list[DailyWellness] = []
        cur = start
        while cur <= end:
            out.append(DailyWellness(
                source=self.name, day=cur, steps=8000,
                resting_hr=52, stress_avg=25,
                body_battery_high=85, body_battery_low=20,
                raw={"stub": True},
            ))
            cur += timedelta(days=1)
        return out

    async def fetch_metrics(self, start: date, end: date) -> Sequence[MetricPoint]:
        self.metric_calls.append((start, end))
        out: list[MetricPoint] = []
        cur = start
        while cur <= end:
            out.append(MetricPoint(source=self.name, day=cur, metric="vo2max", value=52.0))
            out.append(MetricPoint(source=self.name, day=cur, metric="hrv", value=55.0))
            cur += timedelta(days=1)
        return out


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("FITNESS_MCP_DB_PATH", str(db_path))
    monkeypatch.setenv("GARMIN_PERSONAL_API_KEY", "test-key-not-used")
    config.reset_settings_cache()
    db_module.reset_connection()
    yield db_path
    db_module.reset_connection()


@pytest.fixture
def fake_provider(tmp_db):
    p = FakeProvider()
    default_registry.override("garmin", p)
    yield p
    default_registry._instances.pop("garmin", None)
