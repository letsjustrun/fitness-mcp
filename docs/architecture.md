# Architecture

## One-paragraph version

An MCP server runs as a long-running HTTP service. Each tool call parses dates, asks the **sync layer** which days are stale, triggers a **provider fetch** for the narrow stale range only, upserts into **SQLite**, and then answers from SQLite. The provider layer is an abstraction so Garmin can be joined by Strava, Coros, Apple Health, etc. without the rest of the code changing.

```
MCP client (Claude Desktop / Code / claude.ai web)
        │  HTTPS, Authorization: Bearer <token>
┌───────▼──────────────────────────────────────────────────────┐
│  http_server.py   (Starlette: bearer auth, CORS, /healthz)   │
│      │                                                       │
│      ▼                                                       │
│  server.py        (MCPServer app, tool registration only)    │
│      │                                                       │
│      ▼                                                       │
│  tools/*   (parse → clamp → trigger sync → query → return)   │
│      │                                                       │
│      ├── store/sync.py  ──┐                                  │
│      │                     │  (only on cache miss)           │
│      │                     ▼                                 │
│      │               providers/garmin.py  ─► Garmin API      │
│      │                                                       │
│      ▼                                                       │
│  store/queries.py  ─► SQLite ~/.fitness_mcp/data.db          │
└──────────────────────────────────────────────────────────────┘
```

## Why these choices

- **MCP SDK over hand-rolled JSON-RPC.** The SDK handles capability negotiation, Streamable HTTP + SSE framing, and schema generation from Python type hints. A new tool is a decorated async function.
- **SQLite over anything else.** Single file, zero setup, WAL means reads don't block writes. The cache is small (months of data → MB, not GB).
- **HTTP transport only.** One long-running server, many clients. stdio was dropped — if a client cannot dial a URL natively, `mcp-remote` on the client side is a universal stdio ⇄ HTTP proxy. The server never speaks stdio.
- **Cache-aside, not read-through.** We avoid a background sync worker; the tool call *is* the trigger. Downside: first call to a cold range is slower. Upside: no scheduler, no credentials-at-rest-while-idle, no state to reconcile.
- **Provider interface.** Normalizing to one schema is what makes "steps per week in 2026 across Garmin and Strava" a one-line SQL.

## Component responsibilities (strict)

| Layer | Owns | Must NOT |
|---|---|---|
| `server.py` | Tool registration, docstrings, run loop | Business logic, raw HTTP, SQL |
| `http_server.py` | ASGI wiring: bearer auth, CORS, `/healthz`, uvicorn | Business logic, SQL |
| `tools/*.py` | Input validation, orchestration, response shape | Direct provider calls, raw SQL |
| `store/sync.py` | Staleness math, fetch orchestration, upserts | HTTP, upstream shapes |
| `store/queries.py` | Read SQL and response formatting | Writes, network |
| `store/db.py` | Connection, schema apply, transaction scope | Business logic |
| `providers/base.py` | The contract | Anything concrete |
| `providers/<x>.py` | Auth, HTTP, normalization to unified schema | SQL, filesystem, globals |
| `config.py` | Env loading only | Anything stateful beyond cached settings |

## Freshness rules (implemented in `store/sync.py`)

| Day age | Window |
|---|---|
| Today | 30 min |
| 1–3 days ago | 6 h |
| > 3 days ago | Never refreshes once fetched |

Rationale: watches sync late in the evening; Garmin finalizes sleep/HRV the following morning. Older history is immutable, so re-fetching is wasted bandwidth.

`force_refresh=True` on any tool bypasses the window check for its range only.

## Range clamping

`FITNESS_MCP_MAX_RANGE_DAYS` (default 90) caps how many days a single tool call can request. If the caller asks for more, we clamp silently and the response reports `"range.clamped": true`. This protects the provider (fewer surprise multi-year fetches) and the model (predictable payload size).

## Error semantics

All tool entrypoints wrap the body in a try/except. Known failures (bad input, auth, upstream 4xx/5xx) return:

```json
{"error": {"type": "ProviderAuthError", "message": "Garmin rejected the Personal API key. ..."}}
```

Unknown exceptions are logged to stderr and return `type: "InternalError"` with a generic message — no stack traces to the model.

## Data model

See `src/fitness_mcp/store/schema.sql`. Every row has `source` so multi-provider aggregation is one `GROUP BY` away. `raw` columns keep the original provider payload as JSON so we can add derived fields later without re-fetching.

## Scaling path

Where we are: one HTTP server, one shared bearer token, one Garmin account whose key is in the server's env. Perfect for personal use across your own devices.

To take strangers: add OAuth 2.1 on the MCP server (SDK's `token_verifier` / `auth_server_provider` hooks), add a `user_id` column to every table, and switch Garmin credentials to a per-user secret store (each user brings their own Personal API key, since Garmin's Personal API is own-data-only by design). The provider interface, unified schema, cache-aside sync, and HTTP wrapping all survive the transition.
