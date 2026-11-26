# Adding a provider

Walk-through using "Strava" as the hypothetical new provider. Replace the string accordingly.

## 1. Subclass `Provider`

Create `src/fitness_mcp/providers/strava.py`. Implement the five async methods from `providers/base.py`. Normalize every response into the Pydantic models in `models.py` — do not return raw provider shapes from these methods. Set `self.name = "strava"`; that string ends up in the `source` column of every row.

```python
from datetime import date
from typing import Sequence

from ..models import Activity, DailyWellness, MetricPoint, SleepNight
from .base import Provider


class StravaProvider(Provider):
    name = "strava"

    def __init__(self, access_token: str, http_timeout: float = 30.0) -> None:
        ...

    async def fetch_activities(self, start: date, end: date) -> Sequence[Activity]:
        ...
    # ... other methods
```

See `providers/garmin.py` for the shape of a real implementation: token caching, retry on 401, defensive normalization helpers, and `VERIFY_SWAGGER` comments where endpoint strings must be confirmed.

## 2. Add settings

Edit `config.py`:

```python
strava_access_token: str | None = Field(default=None, alias="STRAVA_ACCESS_TOKEN")
strava_refresh_token: str | None = Field(default=None, alias="STRAVA_REFRESH_TOKEN")
```

Add matching entries to `.env.example` so a human knows what to set.

## 3. Register the factory

Edit `providers/registry.py`:

```python
def _strava_factory() -> Provider:
    s = get_settings()
    if not s.strava_access_token:
        raise ProviderAuthError("STRAVA_ACCESS_TOKEN not set.")
    return StravaProvider(access_token=s.strava_access_token,
                          http_timeout=s.http_timeout_seconds)


default_registry.register("strava", _strava_factory)
```

Lazy by design: missing Strava credentials don't break the Garmin path.

## 4. (Optional) expose per-source tool arguments

Tools already accept `source: str = "garmin"`. The MCP `server.py` wires only Garmin by default. If you want callers to pick, re-register the tools with an extra argument, or add dedicated tools (`get_strava_activities`, …). Prefer the first: fewer tools, smaller model prompt.

## 5. Add a smoke test

Create `tests/test_strava_provider.py`. Mock the Strava HTTP calls with `httpx.MockTransport` or similar; assert that a sample response normalizes to the expected `Activity`. See `tests/conftest.py::FakeProvider` for the stub pattern that covers the full interface.

## 6. Update docs

- `README.md`: add Strava to the quick-start.
- `docs/mcp-tools.md`: note that `source="strava"` is now valid.
- `CLAUDE.md`: add any non-obvious provider quirks (rate limits, pagination edges).

## Rules of thumb

- A provider **never** writes to SQLite.
- A provider **always** returns records already matching the unified schema — not raw dicts.
- If the upstream has a metric unique to it (say Strava's "suffer score"), put it in `metrics(source, day, metric, value)` and add it to `_METRIC_SOURCES` in `queries.py`. Do not grow the wellness table for one-off columns.
- Keep raw payloads in the `raw` column. Future features live there before they move into a real column.
