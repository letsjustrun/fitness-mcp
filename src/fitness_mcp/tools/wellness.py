from __future__ import annotations

from ..config import get_settings
from ..providers.registry import get_garmin_provider
from ..store import queries, sync
from ._shared import clamp_range, error_payload, parse_date


async def daily_summary(
    start: str, end: str, force_refresh: bool, source: str = "garmin",
) -> dict:
    try:
        s, e = parse_date(start), parse_date(end)
        settings = get_settings()
        s, e, clamped = clamp_range(s, e, settings.max_range_days)

        provider, tenant = await get_garmin_provider()
        wellness = await sync.sync_wellness(provider, tenant, s, e, force=force_refresh)
        sleep = await sync.sync_sleep(provider, tenant, s, e, force=force_refresh)
        rows = queries.daily_summary(tenant, s, e, source=source)
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
