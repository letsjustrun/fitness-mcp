"""Shared test fixtures.

Each test runs against an isolated SQLite file in a tmp dir and a FakeProvider
registered under a known tenant_id — no network calls, no real Garmin
credentials.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta

import pytest

from fitness_mcp import config
from fitness_mcp.auth import (
    current_garmin_key,
    current_tenant_id,
    tenant_id_from_key,
)
from fitness_mcp.models import (
    Activity,
    BodyBatteryDay,
    DailyWellness,
    HydrationDay,
    MetricPoint,
    SleepNight,
    StressDay,
    WeightMeasurement,
)
from fitness_mcp.providers import registry
from fitness_mcp.providers.base import Provider
from fitness_mcp.store import db as db_module


#: Deterministic key used by the fake provider. Tests can derive its tenant_id
#: via tenant_id_from_key() — exported as `FAKE_TENANT` below.
FAKE_KEY = "test-key-not-used-for-real-garmin-calls"
FAKE_TENANT = tenant_id_from_key(FAKE_KEY)


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
                km=10.0, minutes=55.0,
                avg_hr=150, max_hr=175,
                elevation_m=50.0, training_load=120.0,
                avg_cadence=172, max_cadence=184,
                avg_ground_contact_ms=250,
                avg_vertical_oscillation_cm=8.1,
                avg_vertical_ratio=9.2,
                avg_stride_length_cm=120.0,
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

    async def fetch_body_battery(self, start, end):
        out: list[BodyBatteryDay] = []
        cur = start
        while cur <= end:
            out.append(BodyBatteryDay(source=self.name, day=cur,
                                       min_value=20, max_value=85,
                                       charged=60, drained=55, latest=25))
            cur += timedelta(days=1)
        return out

    async def fetch_stress(self, start, end):
        out: list[StressDay] = []
        cur = start
        while cur <= end:
            out.append(StressDay(source=self.name, day=cur,
                                 avg_level=25, max_level=70,
                                 rest_sec=60_000, activity_sec=40_000,
                                 low_sec=20_000, medium_sec=10_000, high_sec=1_000))
            cur += timedelta(days=1)
        return out

    async def fetch_weight(self, start, end):
        out: list[WeightMeasurement] = []
        cur = start
        while cur <= end:
            out.append(WeightMeasurement(
                source=self.name, day=cur,
                taken_at=datetime.combine(cur, datetime.min.time()),
                weight_kg=72.5, bmi=22.0, body_fat_pct=15.0,
                muscle_mass_kg=34.0, bone_mass_kg=3.2, body_water_pct=60.0,
            ))
            cur += timedelta(days=1)
        return out

    async def fetch_hydration(self, start, end):
        out: list[HydrationDay] = []
        cur = start
        while cur <= end:
            out.append(HydrationDay(source=self.name, day=cur,
                                     consumed_ml=2200, goal_ml=2500))
            cur += timedelta(days=1)
        return out

    async def fetch_hrv_night(self, day):
        return {"calendarDate": day.isoformat(), "lastNightAvg": 95, "stub": True}

    async def fetch_activity_workouts(self, activity_id):
        return {"activityId": activity_id, "workouts": [], "stub": True}

    async def fetch_fitness_age(self, day):
        return MetricPoint(source=self.name, day=day, metric="fitness_age", value=35.0)


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("FITNESS_MCP_DB_PATH", str(db_path))
    config.reset_settings_cache()
    db_module.reset_connection()
    yield db_path
    db_module.reset_connection()


@pytest.fixture
def fake_provider(tmp_db):
    """Register a FakeProvider for the FAKE_TENANT and set the context vars
    so tools resolve it without ever instantiating the real GarminProvider.
    """
    p = FakeProvider()
    registry.set_test_provider(FAKE_TENANT, p)

    key_token = current_garmin_key.set(FAKE_KEY)
    tenant_token = current_tenant_id.set(FAKE_TENANT)

    yield p

    current_garmin_key.reset(key_token)
    current_tenant_id.reset(tenant_token)
    registry.clear_test_providers()
