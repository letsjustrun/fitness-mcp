"""Single-shot read-through tools — fitness age, HRV night detail, activity
workouts. These bypass the SQLite cache because the upstream endpoints are
cheap and the data isn't bulk-queried."""
from __future__ import annotations

from ..providers.registry import get_garmin_provider
from ._shared import error_payload, parse_date


async def fitness_age(day: str) -> dict:
    try:
        d = parse_date(day)
        provider, _ = await get_garmin_provider()
        point = await provider.fetch_fitness_age(d)
        if point is None:
            return {"day": d.isoformat(), "fitness_age": None, "raw": {}}
        return {
            "day": d.isoformat(),
            "fitness_age": point.value,
            "raw": point.raw,
        }
    except Exception as err:  # noqa: BLE001
        return error_payload(err)


async def hrv_night_detail(day: str) -> dict:
    try:
        d = parse_date(day)
        provider, _ = await get_garmin_provider()
        raw = await provider.fetch_hrv_night(d)
        return {"day": d.isoformat(), "detail": raw}
    except Exception as err:  # noqa: BLE001
        return error_payload(err)


async def activity_workouts(activity_id: str) -> dict:
    try:
        provider, _ = await get_garmin_provider()
        raw = await provider.fetch_activity_workouts(activity_id)
        return {"activity_id": activity_id, "workouts": raw}
    except Exception as err:  # noqa: BLE001
        return error_payload(err)
