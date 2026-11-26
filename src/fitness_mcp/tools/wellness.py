from __future__ import annotations

from ..config import get_settings
from ..providers.registry import default_registry
from ..store import queries, sync
from ._shared import clamp_range, error_payload, parse_date


async def daily_summary(
    start: str, end: str, force_refresh: bool, source: str = "garmin",
) -> dict:
    """Wellness + sleep merged by day. Triggers a sync for both kinds."""
    try:
        s, e = parse_date(start), parse_date(end)
        settings = get_settings()
        s, e, clamped = clamp_range(s, e, settings.max_range_days)

        provider = default_registry.get(source)
        wellness = await sync.sync_wellness(provider, s, e, force=force_refresh)
        sleep = await sync.sync_sleep(provider, s, e, force=force_refresh)

        rows = queries.daily_summary(s, e, source=source)
        return {
            "days": rows,
            "range": {"start": s.isoformat(), "end": e.isoformat(), "clamped": clamped},
            "source": source,
            "fetched_from_provider": {
                "wellness": wellness.fetched_records,
                "sleep": sleep.fetched_records,
            },
            "stale_days_resynced": {
                "wellness": wellness.stale_days,
                "sleep": sleep.stale_days,
            },
        }
    except Exception as err:  # noqa: BLE001
        return error_payload(err)
