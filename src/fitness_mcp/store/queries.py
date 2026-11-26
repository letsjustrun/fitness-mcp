"""Read-side queries that back MCP tools.

Keep output compact — the LLM reads this and we don't want to burn context on
raw JSON blobs. Raw provider payloads live in the `raw` column and are only
returned by `activity_detail()`.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from typing import Any

from .db import get_db


def _parse_raw(d: dict[str, Any]) -> dict[str, Any]:
    if d.get("raw"):
        try:
            d["raw"] = json.loads(d["raw"])
        except (TypeError, ValueError):
            pass
    return d


# -------- activities -------------------------------------------------------

def list_activities(
    start: date, end: date, sport: str | None = None, source: str | None = None
) -> list[dict]:
    sql = (
        "SELECT source,id,day,sport,name,start,km,minutes,"
        "avg_hr,max_hr,elevation_m,training_load "
        "FROM activities WHERE day BETWEEN ? AND ?"
    )
    params: list[Any] = [start.isoformat(), end.isoformat()]
    if sport:
        sql += " AND lower(sport) = lower(?)"
        params.append(sport)
    if source:
        sql += " AND source = ?"
        params.append(source)
    sql += " ORDER BY start DESC, day DESC"
    with get_db() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def activity_detail(activity_id: str, source: str | None = None) -> dict | None:
    sql = "SELECT * FROM activities WHERE id = ?"
    params: list[Any] = [activity_id]
    if source:
        sql += " AND source = ?"
        params.append(source)
    with get_db() as conn:
        row = conn.execute(sql, params).fetchone()
    return _parse_raw(dict(row)) if row else None


# -------- sleep ------------------------------------------------------------

def list_sleep(start: date, end: date, source: str | None = None) -> list[dict]:
    sql = (
        "SELECT source,day,hours,deep_min,rem_min,light_min,awake_min,score "
        "FROM sleep WHERE day BETWEEN ? AND ?"
    )
    params: list[Any] = [start.isoformat(), end.isoformat()]
    if source:
        sql += " AND source = ?"
        params.append(source)
    sql += " ORDER BY day DESC"
    with get_db() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


# -------- daily wellness + merged daily summary ----------------------------

def list_wellness(start: date, end: date, source: str | None = None) -> list[dict]:
    sql = (
        "SELECT source,day,steps,resting_hr,stress_avg,"
        "body_battery_high,body_battery_low "
        "FROM daily_wellness WHERE day BETWEEN ? AND ?"
    )
    params: list[Any] = [start.isoformat(), end.isoformat()]
    if source:
        sql += " AND source = ?"
        params.append(source)
    sql += " ORDER BY day DESC"
    with get_db() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def daily_summary(start: date, end: date, source: str | None = None) -> list[dict]:
    """Left-join wellness + sleep by (source, day) so a single row shows both."""
    sql = (
        "SELECT w.source AS source, w.day AS day, "
        "       w.steps, w.resting_hr, w.stress_avg, "
        "       w.body_battery_high, w.body_battery_low, "
        "       s.hours AS sleep_hours, s.score AS sleep_score, "
        "       s.deep_min, s.rem_min, s.light_min, s.awake_min "
        "FROM daily_wellness w "
        "LEFT JOIN sleep s ON s.source = w.source AND s.day = w.day "
        "WHERE w.day BETWEEN ? AND ?"
    )
    params: list[Any] = [start.isoformat(), end.isoformat()]
    if source:
        sql += " AND w.source = ?"
        params.append(source)
    sql += " ORDER BY w.day DESC"
    with get_db() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


# -------- trends -----------------------------------------------------------

#: metric name -> (table, column, aggregation)
_METRIC_SOURCES: dict[str, tuple[str, str, str]] = {
    "resting_hr":        ("daily_wellness", "resting_hr",        "avg"),
    "steps":             ("daily_wellness", "steps",             "sum"),
    "stress_avg":        ("daily_wellness", "stress_avg",        "avg"),
    "body_battery_high": ("daily_wellness", "body_battery_high", "avg"),
    "body_battery_low":  ("daily_wellness", "body_battery_low",  "avg"),
    "sleep_score":       ("sleep",          "score",             "avg"),
    "sleep_hours":       ("sleep",          "hours",             "avg"),
    "training_load":     ("activities",     "training_load",     "sum"),
}


def known_metrics() -> list[str]:
    """Metrics the trends tool knows about, plus ones held in the metrics table."""
    with get_db() as conn:
        extra = [r["metric"] for r in conn.execute("SELECT DISTINCT metric FROM metrics").fetchall()]
    return sorted(set(_METRIC_SOURCES) | set(extra))


def trend(
    metric: str, start: date, end: date, bucket: str, source: str | None = None
) -> list[dict]:
    if bucket not in {"day", "week", "month"}:
        raise ValueError(f"bucket must be day/week/month, got {bucket!r}")

    # Pull raw day-level points, then bucket + aggregate in Python so SQL
    # stays portable and buckets line up with ISO weeks regardless of DB locale.
    if metric in _METRIC_SOURCES:
        table, col, agg = _METRIC_SOURCES[metric]
        sql = (
            f"SELECT day, {col} AS value FROM {table} "
            f"WHERE day BETWEEN ? AND ? AND {col} IS NOT NULL"
        )
        params: list[Any] = [start.isoformat(), end.isoformat()]
    else:
        table, col, agg = "metrics", "value", "avg"
        sql = (
            "SELECT day, value FROM metrics "
            "WHERE metric = ? AND day BETWEEN ? AND ? AND value IS NOT NULL"
        )
        params = [metric, start.isoformat(), end.isoformat()]

    if source:
        sql += " AND source = ?"
        params.append(source)

    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()

    buckets: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        try:
            d = date.fromisoformat(r["day"])
        except ValueError:
            continue
        v = r["value"]
        if v is None:
            continue
        buckets[_bucket_key(d, bucket)].append(float(v))

    out: list[dict] = []
    for key in sorted(buckets):
        vals = buckets[key]
        aggregate = sum(vals) if agg == "sum" else sum(vals) / len(vals)
        out.append({"bucket": key, "value": round(aggregate, 3), "n": len(vals)})
    return out


def _bucket_key(d: date, bucket: str) -> str:
    if bucket == "day":
        return d.isoformat()
    if bucket == "week":
        iso = d.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    return f"{d.year}-{d.month:02d}"
