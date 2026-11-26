"""Garmin Connect Personal API adapter.

Built on Garmin's official client `garmin-connect-personal-api-python`
(package `garmin_personal_api`), so we do not maintain endpoint strings or
response shapes ourselves — the client owns both.

Our job here:
1. Hold the user's Personal API key and hand it to `PersonalApiAuthenticator`
   (which exchanges it for a 24-hour bearer and caches it on disk).
2. Wrap the client's sync methods in `asyncio.to_thread` so they fit our
   async `Provider` interface.
3. Thread a custom CA bundle through the shared `requests.Session` so we work
   on networks with TLS inspection (Zscaler, Netskope, …).
4. Normalize the official client's JSON into our unified models.

The authenticator caches the bearer in
`~/.config/garmin/connect-personal-api-bearer-token.json`. A 401 on any data
endpoint re-obtains the token once and retries.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime
from typing import Any, Sequence

import requests
from garmin_personal_api import (
    GarminPersonalApiClient,
    GarminPersonalApiError,
    HttpError,
    PersonalApiAuthenticator,
)

from ..errors import ProviderAuthError, ProviderFetchError
from ..models import Activity, DailyWellness, MetricPoint, SleepNight
from .base import Provider

log = logging.getLogger(__name__)


class GarminProvider(Provider):
    name = "garmin"

    def __init__(
        self,
        api_key: str,
        http_timeout: float = 30.0,
        ca_bundle: str | None = None,
        token_cache_file: str | None = None,
    ) -> None:
        if not api_key:
            raise ProviderAuthError(
                "Garmin Personal API key is empty. In HTTP mode, Claude must "
                "send 'Authorization: Bearer <your-garmin-key>'. In stdio mode, "
                "set GARMIN_PERSONAL_API_KEY in .env."
            )
        self._api_key = api_key
        self._timeout = http_timeout
        self._session = requests.Session()
        if ca_bundle:
            self._session.verify = ca_bundle
        auth_kwargs: dict[str, object] = {
            "timeout": http_timeout,
            "session": self._session,
        }
        if token_cache_file is not None:
            auth_kwargs["bearer_token_cache_file"] = token_cache_file
        self._authenticator = PersonalApiAuthenticator(**auth_kwargs)
        self._client: GarminPersonalApiClient | None = None
        self._lock = asyncio.Lock()

    async def close(self) -> None:
        def _shutdown() -> None:
            if self._client is not None:
                try:
                    self._client.close()
                except Exception:  # noqa: BLE001
                    pass
            try:
                self._authenticator.close()
            except Exception:  # noqa: BLE001
                pass
            self._session.close()

        await asyncio.to_thread(_shutdown)

    # ------------------------------------------------------------------ auth

    async def _obtain_client(self, force_refresh: bool = False) -> GarminPersonalApiClient:
        async with self._lock:
            if self._client is not None and not force_refresh:
                return self._client
            log.info(
                "%s: %s Garmin bearer token",
                self.name,
                "refreshing" if self._client is not None else "obtaining",
            )
            try:
                bearer = await asyncio.to_thread(
                    self._authenticator.obtain_token,
                    self._api_key,
                    force_refresh=force_refresh,
                )
            except HttpError as e:
                raise self._translate_auth(e) from e
            except GarminPersonalApiError as e:
                raise ProviderAuthError(str(e)) from e
            if self._client is None:
                self._client = GarminPersonalApiClient(
                    bearer_token=bearer.access_token,
                    timeout=self._timeout,
                    session=self._session,
                )
            else:
                self._client.update_bearer_token(bearer.access_token)
            return self._client

    async def _call(self, fn_name: str, /, *args, **kwargs) -> Any:
        """Call a method on the official client, refreshing on 401 once."""
        client = await self._obtain_client()
        try:
            return await asyncio.to_thread(getattr(client, fn_name), *args, **kwargs)
        except HttpError as e:
            if _is_401(e):
                log.info("Garmin returned 401; refreshing bearer and retrying once")
                client = await self._obtain_client(force_refresh=True)
                try:
                    return await asyncio.to_thread(getattr(client, fn_name), *args, **kwargs)
                except HttpError as inner:
                    raise self._translate_fetch(fn_name, inner) from inner
            raise self._translate_fetch(fn_name, e) from e
        except GarminPersonalApiError as e:
            raise ProviderFetchError(f"Garmin {fn_name}: {e}") from e

    # ----------------------------------------------------------------- fetch

    async def fetch_activities(self, start: date, end: date) -> Sequence[Activity]:
        raw = await self._call(
            "search_activities",
            start_date=start,
            end_date=end,
            start=0,
            limit=100,
        )
        return [self._to_activity(item) for item in _as_list(raw)]

    async def fetch_activity_detail(self, activity_id: str) -> dict:
        return await self._call("get_activity", activity_id)

    async def fetch_sleep(self, start: date, end: date) -> Sequence[SleepNight]:
        raw = await self._call("get_daily_sleep_summaries", start, end)
        return [self._to_sleep(item) for item in _as_list(raw)]

    async def fetch_daily_wellness(self, start: date, end: date) -> Sequence[DailyWellness]:
        raw = await self._call("get_daily_summaries", start, end)
        return [self._to_wellness(item) for item in _as_list(raw)]

    async def fetch_metrics(self, start: date, end: date) -> Sequence[MetricPoint]:
        """VO2max + HRV per day. Each sub-fetch is defensive — if the user
        has never recorded that metric, we log and continue.
        """
        points: list[MetricPoint] = []
        try:
            raw = await self._call("get_daily_vo2_max", start, end)
            for item in _as_list(raw):
                pt = self._to_vo2max(item)
                if pt is not None:
                    points.append(pt)
        except ProviderFetchError as e:
            log.warning("skipping vo2max: %s", e)

        try:
            raw = await self._call("get_daily_hrv_summaries", start, end)
            for item in _as_list(raw):
                pt = self._to_hrv(item)
                if pt is not None:
                    points.append(pt)
        except ProviderFetchError as e:
            log.warning("skipping hrv: %s", e)

        return points

    # -------------------------------------------------------------- normalize

    def _to_activity(self, item: dict) -> Activity:
        start_s = item.get("startTimeLocal") or item.get("startTimeGMT")
        start_dt = _parse_dt(start_s)
        sport_val = item.get("activityType")
        if isinstance(sport_val, dict):
            sport = sport_val.get("typeKey")
        else:
            sport = sport_val or item.get("sport")
        return Activity(
            source=self.name,
            id=str(item.get("activityId") or item.get("id") or ""),
            day=(start_dt.date() if start_dt else _today()),
            sport=sport,
            name=item.get("activityName") or item.get("name"),
            start=start_dt,
            km=_meters_to_km(item.get("distance")),
            minutes=_seconds_to_minutes(item.get("duration")),
            avg_hr=_as_int(item.get("averageHR")),
            max_hr=_as_int(item.get("maxHR")),
            elevation_m=_as_float(item.get("elevationGain")),
            training_load=_as_float(item.get("activityTrainingLoad")),
            raw=item,
        )

    def _to_sleep(self, item: dict) -> SleepNight:
        # Garmin's Personal API: overall sleep score lives at
        # sleepScores.overall.value; older keys kept as fallbacks.
        score = (
            _dig(item, "sleepScores", "overall", "value")
            or (item.get("sleepScore") if not isinstance(item.get("sleepScore"), dict)
                else item.get("sleepScore", {}).get("value"))
        )
        return SleepNight(
            source=self.name,
            day=_parse_date(item.get("calendarDate")) or _today(),
            hours=_seconds_to_hours(item.get("sleepTimeSeconds")),
            deep_min=_seconds_to_min(item.get("deepSleepSeconds")),
            rem_min=_seconds_to_min(item.get("remSleepSeconds")),
            light_min=_seconds_to_min(item.get("lightSleepSeconds")),
            awake_min=_seconds_to_min(item.get("awakeSleepSeconds")),
            score=_as_int(score),
            raw=item,
        )

    def _to_wellness(self, item: dict) -> DailyWellness:
        # Garmin's Personal API returns wellness as a nested document.
        return DailyWellness(
            source=self.name,
            day=_parse_date(item.get("calendarDate")) or _today(),
            steps=_as_int(_dig(item, "movement", "steps", "value")),
            resting_hr=_as_int(_dig(item, "heartRate", "restingValue")),
            stress_avg=_as_int(_dig(item, "stress", "avgLevel")),
            body_battery_high=_as_int(_dig(item, "bodyBattery", "maxValue")),
            body_battery_low=_as_int(_dig(item, "bodyBattery", "minValue")),
            raw=item,
        )

    def _to_vo2max(self, item: dict) -> MetricPoint | None:
        # Shape: {"generic": {calendarDate, vo2MaxPreciseValue, vo2MaxValue, ...}, "cycling": null|{...}}
        # Prefer the running/generic reading; fall back to cycling if that's all we have.
        for key in ("generic", "cycling"):
            sub = item.get(key)
            if isinstance(sub, dict) and sub.get("calendarDate") is not None:
                return MetricPoint(
                    source=self.name,
                    day=_parse_date(sub.get("calendarDate")) or _today(),
                    metric="vo2max",
                    value=_as_float(sub.get("vo2MaxPreciseValue") or sub.get("vo2MaxValue")),
                    raw=item,
                )
        return None

    def _to_hrv(self, item: dict) -> MetricPoint | None:
        # Shape: {calendarDate, lastNightAvg, weeklyAvg, ...}
        if not item.get("calendarDate"):
            return None
        return MetricPoint(
            source=self.name,
            day=_parse_date(item.get("calendarDate")) or _today(),
            metric="hrv",
            value=_as_float(item.get("lastNightAvg") or item.get("weeklyAvg")),
            raw=item,
        )

    # -------------------------------------------------------------- errors

    @staticmethod
    def _translate_auth(e: HttpError) -> ProviderAuthError:
        status = _http_status(e)
        if status in (401, 403):
            return ProviderAuthError(
                "Garmin rejected the Personal API key. Create a new key in "
                "Garmin Connect (Settings > Account > Personal API Token) and "
                "update .env."
            )
        return ProviderAuthError(f"Garmin token exchange failed ({status}): {e}")

    @staticmethod
    def _translate_fetch(fn_name: str, e: HttpError) -> ProviderFetchError:
        status = _http_status(e)
        return ProviderFetchError(f"Garmin {fn_name} returned {status}: {e}")


# -- small helpers ----------------------------------------------------------

def _http_status(e: HttpError) -> int | None:
    for attr in ("status_code", "status", "code"):
        v = getattr(e, attr, None)
        if isinstance(v, int):
            return v
    return None


def _is_401(e: HttpError) -> bool:
    return _http_status(e) == 401


def _dig(d: Any, *keys: str) -> Any:
    """Safe nested lookup. Returns None if any key is missing or value is not a dict."""
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def _as_list(raw: Any) -> list[dict]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in (
            "items", "data", "results",
            "activityList", "activities",
            "summaries", "dailySummaries",
            "sleepSummaries", "sleeps",
            "hrvSummaries",
        ):
            if isinstance(raw.get(key), list):
                return raw[key]
        return [raw]
    return []


def _parse_dt(s: Any) -> datetime | None:
    if not isinstance(s, str):
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _parse_date(s: Any) -> date | None:
    if not isinstance(s, str):
        return None
    try:
        return date.fromisoformat(s[:10])
    except (TypeError, ValueError):
        return None


def _as_int(v: Any) -> int | None:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _as_float(v: Any) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _meters_to_km(v: Any) -> float | None:
    f = _as_float(v)
    return round(f / 1000.0, 3) if f is not None else None


def _seconds_to_minutes(v: Any) -> float | None:
    f = _as_float(v)
    return round(f / 60.0, 2) if f is not None else None


def _seconds_to_hours(v: Any) -> float | None:
    f = _as_float(v)
    return round(f / 3600.0, 2) if f is not None else None


def _seconds_to_min(v: Any) -> int | None:
    f = _as_float(v)
    return int(round(f / 60.0)) if f is not None else None


def _today() -> date:
    from datetime import UTC
    return datetime.now(UTC).date()
