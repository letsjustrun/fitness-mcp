# CLAUDE.md — agent working rules for fitness-mcp

> This file is the contract between the human owner and any AI agent editing this repo. Read it in full before making changes.

## Goal
An MCP server that lets Claude (and any MCP-capable AI client) read my fitness data. Start with Garmin only. Strava, Coros and others come later, so keep the design multi-provider.

## Decisions already made (don't revisit without asking)
- **Language/framework:** Python 3.12+, MCP Python SDK. We use `MCPServer` from `mcp.server.mcpserver` — this is the same server type that was named `FastMCP` in SDK v1 and renamed in v2. Treat any legacy "FastMCP" reference as a synonym.
- **Zero-cost POC:** runs on my laptop. SQLite for storage. No paid services.
- **No background sync worker.** Lazy, on-demand "cache-aside" sync:
  a tool call checks SQLite, fetches only missing/stale dates from Garmin, upserts, then answers from SQLite.
- **No client auth for the POC** (between AI client and MCP server). Will add OAuth later.
- **Transport:** Streamable HTTP only. The server binds a URL, speaks JSON-RPC + SSE at `FITNESS_MCP_HTTP_PATH` (default `/mcp`), and all clients connect over HTTP. stdio has been removed; if a client cannot dial a URL natively, use the `mcp-remote` npm shim on the client side — the server never speaks stdio.
  - Default bind is `127.0.0.1`. Binding off localhost requires `FITNESS_MCP_HTTP_BEARER_TOKENS` to be set — the server refuses to start otherwise.
  - CORS off by default. Enable with `FITNESS_MCP_HTTP_CORS_ORIGINS` when claude.ai web needs to reach it.
  - Public exposure before OAuth exists: put it behind a tunnel (e.g. cloudflared), keep the bearer token strong, consider an unguessable URL path.
- **Garmin auth: official Garmin Connect Personal API** (launched Oct 2026), not the unofficial library.
  - I create a Personal API key in Garmin Connect web (Settings > Account > Personal API Token).
  - Key lives in `.env` as `GARMIN_PERSONAL_API_KEY`. Never commit it.
  - Exchange key for a bearer token:
    `POST https://personal.connectapi.garmin.com/personalapitoken-service/personal-api/personal-api-key/token`
    with header `Authorization: ApiKey <key>`. Token valid 24h (or until key expires).
  - Data calls use `Authorization: Bearer <token>`. Cache the token; re-exchange ~1h before expiry; on 401, re-exchange once.
  - Prefer Garmin's official client `garmin-connect-personal-api-python`
    (`PersonalApiAuthenticator`, `GarminPersonalApiClient`) over hand-written HTTP if it covers what we need.
  - Personal API is read-only, pull-only, own data only. Training readiness/recovery may not be available.
  - **Verify endpoint paths and response fields against Garmin's Personal API Swagger docs. Do not guess endpoints.**
  - Unofficial `python-garminconnect` is a fallback ONLY for data the Personal API lacks, and only if I approve it.

## Architecture
```
AI client (Claude Desktop / Claude Code / later claude.ai)
   │ stdio (later: Streamable HTTP)
MCP server (Python, FastMCP) ── tools + cache logic
   │                      │
SQLite (~/.fitness_mcp/data.db)   Garmin Personal API (only on cache miss)
```

Layout (what's in this repo):
```
GarminMCP/
  src/fitness_mcp/
    server.py              # MCPServer app, tool registration, main() → serve_http
    http_server.py         # Starlette wrapping: bearer auth, CORS, /healthz, uvicorn
    config.py              # Settings (pydantic-settings), env loading
    logging_setup.py       # stderr-only logging
    models.py              # Unified Pydantic schema
    errors.py              # Error types shown to the model as clear text
    providers/
      base.py              # Abstract Provider interface
      garmin.py            # Garmin Personal API adapter (auth + fetch + normalize)
      registry.py          # Lazy factory lookup
    store/
      db.py                # SQLite connection, schema apply, transactions
      schema.sql           # DDL
      sync.py              # Staleness detection, upserts, sync_log updates
      queries.py           # Read queries that back tools
    tools/
      _shared.py           # date parsing, error payload, clamping
      activities.py
      sleep.py
      wellness.py
      trends.py
  tests/                   # unit tests, no network
  scripts/
    verify_garmin_token.py # stand-alone token-exchange smoke test
  docs/
    architecture.md
    adding-a-provider.md
    mcp-tools.md
  .env.example
  pyproject.toml
```

## Lazy sync freshness rules
Track fetches in `sync_log(source, kind, day, fetched_at)`.
- Day = today: refetch if older than 30 min.
- Day = yesterday or day before: refetch if older than 6 h (Garmin finalizes sleep/HRV next morning; watches sync late).
- Older than ~3 days: fetch once, never refresh.
- Only fetch stale/missing days. Prefer range calls over per-day calls when the API allows.
- Clamp requested ranges (default max 90 days per call) and tell the caller if clamped.
- Every tool accepts optional `force_refresh: bool`.
- Garmin login/token exchange happens lazily, only when a fetch is actually needed.

Implemented in `store/sync.py`. See `staleness_window()`, `_stale_days()`, `_contiguous_ranges()`.

## Unified schema (every table has `source`; keep `raw` JSON)
- `activities(source, id, day, sport, name, start, km, minutes, avg_hr, max_hr, elevation_m, training_load, raw)`
- `sleep(source, day, hours, deep_min, rem_min, light_min, awake_min, score, raw)`
- `daily_wellness(source, day, steps, resting_hr, stress_avg, body_battery_high, body_battery_low, raw)`
- `metrics(source, day, metric, value, raw)` for VO2max, HRV, weight, etc.
- `sync_log(source, kind, day, fetched_at)`

Map only fields the Personal API actually returns; leave others NULL. Keep `raw` as JSON so we can introduce new derived fields without re-fetching.

## MCP tools (few, high-level, compact output)
- `get_activities(start, end, sport=None, force_refresh=False)` → summary list
- `get_activity_detail(activity_id)` → splits, HR zones if available
- `get_sleep(start, end, force_refresh=False)`
- `get_daily_summary(start, end, force_refresh=False)` → wellness + sleep combined
- `get_trends(metric, start, end, bucket="week")` → aggregation done in SQL/Python
Dates are `YYYY-MM-DD`. Docstrings matter: they are what the model reads to choose tools.
Return summaries, never second-by-second streams by default.

## Rules
- Logs go to stderr via `logging`. Enforced by `logging_setup.configure_logging()`. Stdout is reserved in case we ever re-add a stdio transport — do not `print()`.
- Use absolute URLs in any client config (`http://127.0.0.1:8000/mcp`); never `localhost` without a port if the client doesn't infer defaults.
- Garmin errors return a clear message to the model (e.g. "Garmin rejected the key; create a new one"), not a stack trace. See `errors.py` and the `error_payload()` helper.
- Secrets only in `.env`; `.env` and `*.db` are in `.gitignore`.
- Tests must not make real network calls. Use the `FakeProvider` in `tests/conftest.py`.
- Every endpoint in `providers/garmin.py` that calls real Garmin paths is marked `VERIFY_SWAGGER`. Confirm against Garmin's published Swagger before shipping real credentials.

## Build order
1. ✅ Project skeleton, `.env.example`, SQLite schema, Garmin token exchange.
2. ✅ `get_activities` end to end with lazy sync. Test with `npx @modelcontextprotocol/inspector`.
3. ✅ `get_sleep`, `get_daily_summary`, `get_trends`.
4. Register in Claude Desktop / Claude Code and try real questions.
5. Later: Streamable HTTP + tunnel, then OAuth for clients, then Strava adapter.

## For future agents working here
- Changing the sync windows? Also update `README.md`, `docs/architecture.md`, and the tool docstrings.
- Adding a new MCP tool? Keep its docstring tight — that's the prompt the model sees when picking it. State the inputs, the output shape, and when to prefer it over a neighbour.
- Adding a provider? Follow `docs/adding-a-provider.md` and add a smoke test that mocks the upstream.
- Do not pull in heavy dependencies for a feature that could be ten lines. This is a POC.
