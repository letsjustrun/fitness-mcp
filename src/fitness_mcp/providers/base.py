"""Provider interface.

A `Provider` is a read-only adapter over an upstream fitness service (Garmin,
Strava, Coros, …). Each method fetches raw data for a date range and returns
records already normalized to the unified schema (`models.py`).

Providers never touch SQLite — persistence is owned by `store.sync`. A provider
raises `ProviderAuthError` or `ProviderFetchError` from `errors.py` with a
human-readable message when something goes wrong; those messages get surfaced
verbatim to the MCP client.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import date

from ..models import (
    Activity,
    BodyBatteryDay,
    DailyWellness,
    HydrationDay,
    MetricPoint,
    SleepNight,
    StressDay,
    WeightMeasurement,
)


class Provider(ABC):
    #: Short, stable identifier stored in every DB row under the ``source`` column.
    name: str

    @abstractmethod
    async def fetch_activities(self, start: date, end: date) -> Sequence[Activity]:
        """Return all activities with ``day`` in [start, end], inclusive."""

    @abstractmethod
    async def fetch_activity_detail(self, activity_id: str) -> dict:
        """Return the raw, provider-shaped detail payload for one activity."""

    @abstractmethod
    async def fetch_sleep(self, start: date, end: date) -> Sequence[SleepNight]:
        ...

    @abstractmethod
    async def fetch_daily_wellness(self, start: date, end: date) -> Sequence[DailyWellness]:
        ...

    @abstractmethod
    async def fetch_metrics(self, start: date, end: date) -> Sequence[MetricPoint]:
        """VO2max, HRV, weight, etc. Normalized to one row per (day, metric)."""

    # ---- new daily series ---------------------------------------------------
    # Default no-op implementations so a provider that doesn't support one of
    # these doesn't have to override. Returns empty.

    async def fetch_body_battery(self, start: date, end: date) -> Sequence[BodyBatteryDay]:
        return []

    async def fetch_stress(self, start: date, end: date) -> Sequence[StressDay]:
        return []

    async def fetch_weight(self, start: date, end: date) -> Sequence[WeightMeasurement]:
        return []

    async def fetch_hydration(self, start: date, end: date) -> Sequence[HydrationDay]:
        return []

    # ---- single-shot, no caching -------------------------------------------

    async def fetch_hrv_night(self, day: date) -> dict:
        return {}

    async def fetch_activity_workouts(self, activity_id: str) -> dict:
        return {}

    async def fetch_fitness_age(self, day: date) -> MetricPoint | None:
        return None

    async def close(self) -> None:
        """Release upstream resources. Default no-op."""
        return
