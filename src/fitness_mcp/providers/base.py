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

from ..models import Activity, DailyWellness, MetricPoint, SleepNight


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

    async def close(self) -> None:
        """Release upstream resources. Default no-op."""
        return
