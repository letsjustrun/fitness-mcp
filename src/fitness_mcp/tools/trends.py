from __future__ import annotations

from ..config import get_settings
from ..errors import ValidationError
from ..providers.registry import get_garmin_provider
from ..store import queries, sync
from ._shared import clamp_range, error_payload, parse_date

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

        provider, tenant = await get_garmin_provider()
        sync_kind = _METRIC_TO_SYNC.get(metric, "metrics")
        if sync_kind == "wellness":
            await sync.sync_wellness(provider, tenant, s, e)
        elif sync_kind == "sleep":
            await sync.sync_sleep(provider, tenant, s, e)
        elif sync_kind == "activities":
            await sync.sync_activities(provider, tenant, s, e)
        else:
            await sync.sync_metrics(provider, tenant, s, e)

        series = queries.trend(tenant, metric, s, e, bucket, source=source)
        return {
            "metric": metric,
            "bucket": bucket,
            "range": {"start": s.isoformat(), "end": e.isoformat(), "clamped": clamped},
            "source": source,
            "series": series,
        }
    except Exception as err:  # noqa: BLE001
        return error_payload(err)
