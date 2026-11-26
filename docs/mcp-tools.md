# MCP tool reference

Dates are **`YYYY-MM-DD`**, inclusive on both ends. All tools return a JSON object. Errors are returned as `{"error": {"type": "...", "message": "..."}}` — the model should read the message.

## `get_activities(start, end, sport=None, force_refresh=False)`

Summary list of workouts in the range.

**Returns**

```json
{
  "activities": [
    {
      "source": "garmin", "id": "act-...", "day": "2026-11-23",
      "sport": "running", "name": "Evening Run",
      "start": "2026-11-23T18:04:00", "km": 10.4, "minutes": 55.2,
      "avg_hr": 148, "max_hr": 173, "elevation_m": 52.0,
      "training_load": 118.0
    }
  ],
  "range": {"start": "...", "end": "...", "clamped": false},
  "source": "garmin",
  "fetched_from_provider": 3,
  "stale_days_resynced": 3
}
```

- `sport` is case-insensitive. Common Garmin keys: `running`, `cycling`, `swimming`, `strength_training`, `walking`, `hiking`.
- `force_refresh=true` bypasses the freshness cache for this range only.

## `get_activity_detail(activity_id)`

Full detail for one activity, including the raw provider payload for anything we don't yet unpack (splits, HR zones). If the activity is not in local cache, we fetch directly and return under `activity.raw` without upserting.

## `get_sleep(start, end, force_refresh=False)`

Per-night sleep: `hours`, `deep_min`, `rem_min`, `light_min`, `awake_min`, `score`.

Recent nights automatically refresh because watches sync late and Garmin finalises scoring the next morning.

## `get_daily_summary(start, end, force_refresh=False)`

One row per day joining wellness + sleep:

```json
{
  "days": [
    {
      "source": "garmin", "day": "2026-11-23",
      "steps": 9124, "resting_hr": 51, "stress_avg": 22,
      "body_battery_high": 88, "body_battery_low": 19,
      "sleep_hours": 7.6, "sleep_score": 82,
      "deep_min": 95, "rem_min": 92, "light_min": 268, "awake_min": 8
    }
  ]
}
```

Null fields mean the provider didn't return a value for that day (e.g. the watch wasn't worn, or the metric is unsupported on the Personal API).

## `get_trends(metric, start, end, bucket="week")`

Aggregates one metric over day/week/month buckets.

| Metric | Aggregation |
|---|---|
| `steps` | sum |
| `training_load` | sum |
| `resting_hr`, `stress_avg`, `body_battery_*` | mean |
| `sleep_hours`, `sleep_score` | mean |
| `vo2max`, `hrv`, other entries in the `metrics` table | mean |

`bucket` is one of `"day"`, `"week"`, `"month"`. Weeks are ISO weeks (`YYYY-Www`).

## Range clamping

Every tool clamps the range to `FITNESS_MCP_MAX_RANGE_DAYS` (default 90). `range.clamped: true` in the response means the end date was moved back; call the tool again for the next window if you need the rest.

## Error shape

```json
{"error": {"type": "ProviderAuthError",
           "message": "Garmin rejected the Personal API key. Create a new key in Garmin Connect..."}}
```

Types the model can expect: `ValidationError`, `ProviderAuthError`, `ProviderFetchError`, `InternalError`.
