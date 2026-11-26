"""Tool entrypoints for the extended wellness series: body battery, stress,
weight, hydration."""
from __future__ import annotations

from ..config import get_settings
from ..providers.registry import get_garmin_provider
from ..store import queries, sync
from ._shared import clamp_range, error_payload, parse_date


async def body_battery(start: str, end: str, force_refresh: bool) -> dict:
    try:
        s, e = parse_date(start), parse_date(end)
        settings = get_settings()
        s, e, clamped = clamp_range(s, e, settings.max_range_days)
        provider, tenant = await get_garmin_provider()
        result = await sync.sync_body_battery(provider, tenant, s, e, force=force_refresh)
        rows = queries.list_body_battery(tenant, s, e)
        return {
            "body_battery": rows,
            "range": {"start": s.isoformat(), "end": e.isoformat(), "clamped": clamped},
            "fetched_from_provider": result.fetched_records,
            "stale_days_resynced": result.stale_days,
        }
    except Exception as err:  # noqa: BLE001
        return error_payload(err)


async def stress(start: str, end: str, force_refresh: bool) -> dict:
    try:
        s, e = parse_date(start), parse_date(end)
        settings = get_settings()
        s, e, clamped = clamp_range(s, e, settings.max_range_days)
        provider, tenant = await get_garmin_provider()
        result = await sync.sync_stress(provider, tenant, s, e, force=force_refresh)
        rows = queries.list_stress(tenant, s, e)
        return {
            "stress": rows,
            "range": {"start": s.isoformat(), "end": e.isoformat(), "clamped": clamped},
            "fetched_from_provider": result.fetched_records,
            "stale_days_resynced": result.stale_days,
        }
    except Exception as err:  # noqa: BLE001
        return error_payload(err)


async def weight(start: str, end: str, force_refresh: bool) -> dict:
    try:
        s, e = parse_date(start), parse_date(end)
        settings = get_settings()
        s, e, clamped = clamp_range(s, e, settings.max_range_days)
        provider, tenant = await get_garmin_provider()
        result = await sync.sync_weight(provider, tenant, s, e, force=force_refresh)
        rows = queries.list_weight(tenant, s, e)
        return {
            "weight": rows,
            "range": {"start": s.isoformat(), "end": e.isoformat(), "clamped": clamped},
            "fetched_from_provider": result.fetched_records,
            "stale_days_resynced": result.stale_days,
        }
    except Exception as err:  # noqa: BLE001
        return error_payload(err)


async def hydration(start: str, end: str, force_refresh: bool) -> dict:
    try:
        s, e = parse_date(start), parse_date(end)
        settings = get_settings()
        s, e, clamped = clamp_range(s, e, settings.max_range_days)
        provider, tenant = await get_garmin_provider()
        result = await sync.sync_hydration(provider, tenant, s, e, force=force_refresh)
        rows = queries.list_hydration(tenant, s, e)
        return {
            "hydration": rows,
            "range": {"start": s.isoformat(), "end": e.isoformat(), "clamped": clamped},
            "fetched_from_provider": result.fetched_records,
            "stale_days_resynced": result.stale_days,
        }
    except Exception as err:  # noqa: BLE001
        return error_payload(err)
