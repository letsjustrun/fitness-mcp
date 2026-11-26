"""Recovery signal — a composite score Claude can reason about without
pulling five tools worth of data itself."""
from __future__ import annotations

from datetime import date, timedelta

from ..providers.registry import get_garmin_provider
from ..store import queries, sync
from ._shared import error_payload, parse_date


def _normalise(value: float, low: float, high: float) -> float:
    """Map `value` from [low, high] → [0, 100]. Clips at the edges."""
    if value is None:
        return 50.0  # treat missing as neutral
    span = max(high - low, 1e-9)
    return max(0.0, min(100.0, 100.0 * (value - low) / span))


async def recovery_signal(day: str) -> dict:
    """Composite recovery score for one date.

    Blends (weights in parens):
      - Sleep score          (0.30)
      - HRV last-night vs 7-day median         (0.20)
      - Body battery morning value             (0.15)
      - Resting HR vs 14-day median            (0.15)
      - Yesterday's training load vs 14-day    (0.20)

    Returns the composite 0–100 and every input so Claude can explain
    the number instead of hiding the math.
    """
    try:
        d = parse_date(day)
        provider, tenant = await get_garmin_provider()

        baseline_end = d - timedelta(days=1)
        baseline_start = d - timedelta(days=14)

        # Warm the local cache for the window we'll read from.
        await sync.sync_sleep(provider, tenant, baseline_start, d)
        await sync.sync_wellness(provider, tenant, baseline_start, d)
        await sync.sync_metrics(provider, tenant, baseline_start, d)
        await sync.sync_body_battery(provider, tenant, baseline_start, d)
        await sync.sync_activities(provider, tenant, baseline_start, d)

        sleep_rows = queries.list_sleep(tenant, d, d)
        wellness_rows = queries.list_wellness(tenant, baseline_start, d)
        hrv_series = queries.trend(tenant, "hrv", baseline_start, d, bucket="day")
        bb_rows = queries.list_body_battery(tenant, d, d)
        activities_window = queries.list_activities(
            tenant, baseline_end - timedelta(days=13), baseline_end,
        )

        sleep_score = (sleep_rows[0].get("score") if sleep_rows else None)

        rhr_today = next((w["resting_hr"] for w in wellness_rows
                          if w["day"] == d.isoformat() and w.get("resting_hr") is not None),
                         None)
        rhr_baseline = sorted(
            w["resting_hr"] for w in wellness_rows
            if w["day"] != d.isoformat() and w.get("resting_hr") is not None
        )
        rhr_median = (rhr_baseline[len(rhr_baseline) // 2]
                      if rhr_baseline else None)

        hrv_today = next((p["value"] for p in hrv_series
                          if p.get("bucket") == d.isoformat()), None)
        hrv_baseline = sorted(
            p["value"] for p in hrv_series
            if p.get("bucket") != d.isoformat() and p.get("value") is not None
        )
        hrv_median = (hrv_baseline[len(hrv_baseline) // 2]
                      if hrv_baseline else None)

        bb_morning = bb_rows[0].get("max_value") if bb_rows else None

        yesterday_load = sum(
            (a.get("training_load") or 0) for a in activities_window
            if a["day"] == baseline_end.isoformat()
        ) or None
        load_window = [
            sum(
                (a.get("training_load") or 0) for a in activities_window
                if a["day"] == day_iso
            )
            for day_iso in {a["day"] for a in activities_window}
        ]
        load_median = (sorted(load_window)[len(load_window) // 2]
                       if load_window else None)

        # ---- translate each signal to a 0-100 contribution -----------------
        sleep_component = _normalise(sleep_score, 0, 100) if sleep_score is not None else 50.0

        if hrv_today is not None and hrv_median:
            hrv_delta = (hrv_today - hrv_median) / max(hrv_median, 1) * 100
            hrv_component = _normalise(hrv_delta, -20, 20)
        else:
            hrv_component = 50.0

        bb_component = _normalise(bb_morning, 30, 100) if bb_morning is not None else 50.0

        if rhr_today is not None and rhr_median:
            # Lower RHR than baseline is better → invert.
            rhr_delta = rhr_median - rhr_today
            rhr_component = _normalise(rhr_delta, -5, 5)
        else:
            rhr_component = 50.0

        if yesterday_load is not None and load_median:
            # Less load than median means fresher legs; more load → worse.
            load_delta = load_median - yesterday_load
            load_component = _normalise(load_delta, -load_median, load_median)
        else:
            load_component = 50.0

        composite = (
            0.30 * sleep_component +
            0.20 * hrv_component +
            0.15 * bb_component +
            0.15 * rhr_component +
            0.20 * load_component
        )

        return {
            "day": d.isoformat(),
            "composite_score": round(composite, 1),
            "components": {
                "sleep":          {"score": sleep_component,  "input": sleep_score},
                "hrv":            {"score": hrv_component,
                                   "today": hrv_today, "baseline_median": hrv_median},
                "body_battery":   {"score": bb_component, "morning_max": bb_morning},
                "resting_hr":     {"score": rhr_component,
                                   "today": rhr_today, "baseline_median": rhr_median},
                "training_load":  {"score": load_component,
                                   "yesterday": yesterday_load,
                                   "baseline_median": load_median},
            },
            "advice_hint": _advise(composite),
        }
    except Exception as err:  # noqa: BLE001
        return error_payload(err)


def _advise(score: float) -> str:
    if score >= 75:
        return "fully recovered — green light for hard effort"
    if score >= 60:
        return "well recovered — comfortable with a quality session"
    if score >= 45:
        return "moderate — favour steady-state over intervals"
    if score >= 30:
        return "under-recovered — keep it easy or take an off day"
    return "burnt out — rest day strongly suggested"
