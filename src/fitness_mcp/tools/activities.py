from __future__ import annotations

from ..config import get_settings
from ..providers.registry import default_registry
from ..store import queries, sync
from ._shared import clamp_range, error_payload, parse_date


async def list_activities(
    start: str, end: str, sport: str | None, force_refresh: bool,
    source: str = "garmin",
) -> dict:
    try:
        s, e = parse_date(start), parse_date(end)
        settings = get_settings()
        s, e, clamped = clamp_range(s, e, settings.max_range_days)

        provider = default_registry.get(source)
        result = await sync.sync_activities(provider, s, e, force=force_refresh)
        rows = queries.list_activities(s, e, sport=sport, source=source)
        return {
            "activities": rows,
            "range": {"start": s.isoformat(), "end": e.isoformat(), "clamped": clamped},
            "source": source,
            "fetched_from_provider": result.fetched_records,
            "stale_days_resynced": result.stale_days,
        }
    except Exception as err:  # noqa: BLE001
        return error_payload(err)


async def activity_detail(activity_id: str, source: str = "garmin") -> dict:
    try:
        row = queries.activity_detail(activity_id, source=source)
        if row:
            return {"activity": row, "source": source}
        # Not cached locally — hit the provider directly and return the raw shape.
        provider = default_registry.get(source)
        raw = await provider.fetch_activity_detail(activity_id)
        return {"activity": {"id": activity_id, "raw": raw}, "source": source, "cached": False}
    except Exception as err:  # noqa: BLE001
        return error_payload(err)
