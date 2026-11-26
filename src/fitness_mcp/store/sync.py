"""Lazy cache-aside sync, tenant-scoped.

Every public function takes a `tenant_id` (16-char hex, see auth.py). Every
row we write carries that tenant_id; every row we read is filtered by it.
Users never see each other's data.

Freshness windows (from CLAUDE.md):
    today            → refetch if older than 30 min
    yesterday / -2d  → refetch if older than 6 h
    -3d              → treat as recent (6 h window)
    older            → fetch once, never refresh
"""
from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from ..models import Activity, DailyWellness, MetricPoint, SleepNight
from ..providers.base import Provider
from .db import transaction

log = logging.getLogger(__name__)

WINDOW_TODAY = timedelta(minutes=30)
WINDOW_RECENT = timedelta(hours=6)
RECENT_HORIZON_DAYS = 3


# -------- public API -------------------------------------------------------

@dataclass
class SyncResult:
    stale_days: int
    fetched_records: int


async def sync_activities(
    provider: Provider, tenant_id: str, start: date, end: date, *, force: bool = False,
) -> SyncResult:
    return await _sync(
        provider, tenant_id, "activities", start, end, force,
        provider.fetch_activities, _upsert_activities,
    )


async def sync_sleep(
    provider: Provider, tenant_id: str, start: date, end: date, *, force: bool = False,
) -> SyncResult:
    return await _sync(
        provider, tenant_id, "sleep", start, end, force,
        provider.fetch_sleep, _upsert_sleep,
    )


async def sync_wellness(
    provider: Provider, tenant_id: str, start: date, end: date, *, force: bool = False,
) -> SyncResult:
    return await _sync(
        provider, tenant_id, "daily_wellness", start, end, force,
        provider.fetch_daily_wellness, _upsert_wellness,
    )


async def sync_metrics(
    provider: Provider, tenant_id: str, start: date, end: date, *, force: bool = False,
) -> SyncResult:
    return await _sync(
        provider, tenant_id, "metrics", start, end, force,
        provider.fetch_metrics, _upsert_metrics,
    )


# -------- staleness logic (pure, unit-tested) ------------------------------

def staleness_window(day: date, today: date) -> timedelta | None:
    age = (today - day).days
    if age < 0:
        return WINDOW_TODAY
    if age == 0:
        return WINDOW_TODAY
    if age <= RECENT_HORIZON_DAYS:
        return WINDOW_RECENT
    return None


def is_stale(fetched_at: datetime | None, day: date, today: date, now: datetime) -> bool:
    if fetched_at is None:
        return True
    window = staleness_window(day, today)
    if window is None:
        return False
    return (now - fetched_at) > window


# -------- internal helpers -------------------------------------------------

def _iter_days(start: date, end: date) -> Iterable[date]:
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def _load_sync_log(
    tenant_id: str, source: str, kind: str, start: date, end: date,
) -> dict[date, datetime]:
    with transaction() as conn:
        rows = conn.execute(
            "SELECT day, fetched_at FROM sync_log "
            "WHERE tenant_id=? AND source=? AND kind=? AND day BETWEEN ? AND ?",
            (tenant_id, source, kind, start.isoformat(), end.isoformat()),
        ).fetchall()
    out: dict[date, datetime] = {}
    for r in rows:
        try:
            out[date.fromisoformat(r["day"])] = datetime.fromisoformat(r["fetched_at"])
        except ValueError:
            continue
    return out


def _stale_days(
    tenant_id: str, source: str, kind: str, start: date, end: date,
    today: date, now: datetime, force: bool,
) -> list[date]:
    if force:
        return list(_iter_days(start, end))
    entries = _load_sync_log(tenant_id, source, kind, start, end)
    return [d for d in _iter_days(start, end) if is_stale(entries.get(d), d, today, now)]


def _contiguous_ranges(days: Sequence[date]) -> list[tuple[date, date]]:
    if not days:
        return []
    ranges: list[tuple[date, date]] = []
    start = prev = days[0]
    for d in days[1:]:
        if (d - prev).days == 1:
            prev = d
            continue
        ranges.append((start, prev))
        start = prev = d
    ranges.append((start, prev))
    return ranges


def _write_sync_log(
    tenant_id: str, source: str, kind: str, days: Sequence[date], now: datetime,
) -> None:
    if not days:
        return
    with transaction() as conn:
        conn.executemany(
            "INSERT INTO sync_log(tenant_id, source, kind, day, fetched_at) "
            "VALUES(?,?,?,?,?) "
            "ON CONFLICT(tenant_id, source, kind, day) DO UPDATE SET "
            "fetched_at=excluded.fetched_at",
            [
                (tenant_id, source, kind, d.isoformat(), now.isoformat())
                for d in days
            ],
        )


# -------- upserts ----------------------------------------------------------

def _upsert_activities(tenant_id: str, items: Sequence[Activity]) -> None:
    if not items:
        return
    with transaction() as conn:
        conn.executemany(
            """
            INSERT INTO activities(
                tenant_id, source, id, day, sport, name, start,
                km, minutes, avg_hr, max_hr, elevation_m, training_load,
                avg_cadence, max_cadence, avg_ground_contact_ms,
                avg_vertical_oscillation_cm, avg_vertical_ratio,
                avg_stride_length_cm,
                raw
            )
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(tenant_id, source, id) DO UPDATE SET
                day=excluded.day, sport=excluded.sport, name=excluded.name,
                start=excluded.start, km=excluded.km, minutes=excluded.minutes,
                avg_hr=excluded.avg_hr, max_hr=excluded.max_hr,
                elevation_m=excluded.elevation_m, training_load=excluded.training_load,
                avg_cadence=excluded.avg_cadence,
                max_cadence=excluded.max_cadence,
                avg_ground_contact_ms=excluded.avg_ground_contact_ms,
                avg_vertical_oscillation_cm=excluded.avg_vertical_oscillation_cm,
                avg_vertical_ratio=excluded.avg_vertical_ratio,
                avg_stride_length_cm=excluded.avg_stride_length_cm,
                raw=excluded.raw
            """,
            [
                (
                    tenant_id, a.source, a.id, a.day.isoformat(), a.sport, a.name,
                    a.start.isoformat() if a.start else None,
                    a.km, a.minutes, a.avg_hr, a.max_hr, a.elevation_m, a.training_load,
                    a.avg_cadence, a.max_cadence, a.avg_ground_contact_ms,
                    a.avg_vertical_oscillation_cm, a.avg_vertical_ratio,
                    a.avg_stride_length_cm,
                    json.dumps(a.raw, default=str),
                )
                for a in items
            ],
        )


def _upsert_sleep(tenant_id: str, items: Sequence[SleepNight]) -> None:
    if not items:
        return
    with transaction() as conn:
        conn.executemany(
            """
            INSERT INTO sleep(tenant_id, source, day, hours, deep_min, rem_min,
                              light_min, awake_min, score, raw)
            VALUES(?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(tenant_id, source, day) DO UPDATE SET
                hours=excluded.hours, deep_min=excluded.deep_min,
                rem_min=excluded.rem_min, light_min=excluded.light_min,
                awake_min=excluded.awake_min, score=excluded.score,
                raw=excluded.raw
            """,
            [
                (tenant_id, s.source, s.day.isoformat(), s.hours, s.deep_min,
                 s.rem_min, s.light_min, s.awake_min, s.score,
                 json.dumps(s.raw, default=str))
                for s in items
            ],
        )


def _upsert_wellness(tenant_id: str, items: Sequence[DailyWellness]) -> None:
    if not items:
        return
    with transaction() as conn:
        conn.executemany(
            """
            INSERT INTO daily_wellness(tenant_id, source, day, steps, resting_hr,
                                       stress_avg, body_battery_high,
                                       body_battery_low, raw)
            VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(tenant_id, source, day) DO UPDATE SET
                steps=excluded.steps, resting_hr=excluded.resting_hr,
                stress_avg=excluded.stress_avg,
                body_battery_high=excluded.body_battery_high,
                body_battery_low=excluded.body_battery_low, raw=excluded.raw
            """,
            [
                (tenant_id, w.source, w.day.isoformat(), w.steps, w.resting_hr,
                 w.stress_avg, w.body_battery_high, w.body_battery_low,
                 json.dumps(w.raw, default=str))
                for w in items
            ],
        )


def _upsert_metrics(tenant_id: str, items: Sequence[MetricPoint]) -> None:
    if not items:
        return
    with transaction() as conn:
        conn.executemany(
            """
            INSERT INTO metrics(tenant_id, source, day, metric, value, raw)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(tenant_id, source, day, metric) DO UPDATE SET
                value=excluded.value, raw=excluded.raw
            """,
            [
                (tenant_id, m.source, m.day.isoformat(), m.metric, m.value,
                 json.dumps(m.raw, default=str))
                for m in items
            ],
        )


# -------- core sync loop ---------------------------------------------------

async def _sync(
    provider: Provider,
    tenant_id: str,
    kind: str,
    start: date,
    end: date,
    force: bool,
    fetch: Callable[[date, date], Awaitable[Sequence]],
    upsert: Callable[[str, Sequence], None],
) -> SyncResult:
    now = datetime.now(UTC)
    today = now.date()
    stale = _stale_days(tenant_id, provider.name, kind, start, end, today, now, force)
    if not stale:
        log.debug("%s[%s/%s] %s..%s already fresh", kind, provider.name, tenant_id, start, end)
        return SyncResult(stale_days=0, fetched_records=0)

    total = 0
    for rng_start, rng_end in _contiguous_ranges(stale):
        log.info("fetching %s[%s/%s] %s..%s", kind, provider.name, tenant_id, rng_start, rng_end)
        records = list(await fetch(rng_start, rng_end))
        upsert(tenant_id, records)
        total += len(records)

    _write_sync_log(tenant_id, provider.name, kind, stale, now)
    return SyncResult(stale_days=len(stale), fetched_records=total)
