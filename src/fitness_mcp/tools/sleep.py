from __future__ import annotations

from ..config import get_settings
from ..providers.registry import get_garmin_provider
from ..store import queries, sync
from ._shared import clamp_range, error_payload, parse_date


async def list_sleep(
    start: str, end: str, force_refresh: bool, source: str = "garmin",
) -> dict:
    try:
        s, e = parse_date(start), parse_date(end)
        settings = get_settings()
        s, e, clamped = clamp_range(s, e, settings.max_range_days)

        provider, tenant = await get_garmin_provider()
        result = await sync.sync_sleep(provider, tenant, s, e, force=force_refresh)
        rows = queries.list_sleep(tenant, s, e, source=source)
        return {
            "sleep": rows,
            "range": {"start": s.isoformat(), "end": e.isoformat(), "clamped": clamped},
            "source": source,
            "fetched_from_provider": result.fetched_records,
            "stale_days_resynced": result.stale_days,
        }
    except Exception as err:  # noqa: BLE001
        return error_payload(err)
