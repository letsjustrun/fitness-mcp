from __future__ import annotations

from ..config import get_settings
from ..errors import ValidationError
from ..providers.registry import default_registry
from ..store import queries, sync
from ._shared import clamp_range, error_payload, parse_date

# Which sync kind do we need to run before we can serve a trend for this metric?
_METRIC_TO_SYNC = {
    "resting_hr": "wellness",
    "steps": "wellness",
    "stress_avg": "wellness",
    "body_battery_high": "wellness",
    "body_battery_low": "wellness",
    "sleep_score": "sleep",
    "sleep_hours": "sleep",
    "training_load": "activities",
}


async def trend(
    metric: str, start: str, end: str, bucket: str = "week",
    source: str = "garmin",
) -> dict:
    try:
        s, e = parse_date(start), parse_date(end)
        if bucket not in {"day", "week", "month"}:
            raise ValidationError(f"bucket must be day/week/month, got {bucket!r}")

        settings = get_settings()
        s, e, clamped = clamp_range(s, e, settings.max_range_days)

        provider = default_registry.get(source)
        sync_kind = _METRIC_TO_SYNC.get(metric, "metrics")
        if sync_kind == "wellness":
            await sync.sync_wellness(provider, s, e)
        elif sync_kind == "sleep":
            await sync.sync_sleep(provider, s, e)
        elif sync_kind == "activities":
            await sync.sync_activities(provider, s, e)
        else:
            await sync.sync_metrics(provider, s, e)

        series = queries.trend(metric, s, e, bucket, source=source)
        return {
            "metric": metric,
            "bucket": bucket,
            "range": {"start": s.isoformat(), "end": e.isoformat(), "clamped": clamped},
            "source": source,
            "series": series,
        }
    except Exception as err:  # noqa: BLE001
        return error_payload(err)
