# fitness-mcp

**A Model Context Protocol server that lets Claude read your Garmin fitness data.**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)]()

Ask Claude "how was my training this week?", "is my resting heart rate trending down?", "find me every run over 10 km since April" — and get real answers from your own Garmin data. The server runs on your machine; nothing is uploaded, nothing is shared with the author of this project. **Bring your own Garmin Personal API key.**

Built on the official [`garmin-connect-personal-api-python`](https://pypi.org/project/garmin-connect-personal-api-python/) client — no reverse engineering, no scraping.

```
┌───────────────────────────┐          ┌────────────────────────┐
│ Claude Desktop / Code /   │  stdio   │  fitness-mcp           │
│ claude.ai (via connector) │ ───────► │  (MCP + SQLite cache)  │
└───────────────────────────┘          └──────────┬─────────────┘
                                                  │ Garmin Personal API
                                                  │ (on cache miss only)
                                                  ▼
                                      ┌─────────────────────────┐
                                      │  Garmin Connect         │
                                      └─────────────────────────┘
```

---

## Features

- **Five high-level tools** for activities, sleep, daily wellness, trends, and per-activity detail.
- **Lazy, on-demand sync** — the first call to a fresh date range fetches from Garmin; subsequent calls read from local SQLite. Recent days auto-refresh as Garmin finalises sleep/HRV.
- **Multi-provider by design** — adding Strava, Coros, or Apple Health is a new file under `providers/` and one line of registration.
- **Corporate-friendly** — if your network uses Zscaler/Netskope TLS inspection, point it at your CA bundle and it just works.
- **Two transports** — stdio for local Claude installs (default) or Streamable HTTP for self-hosting.

---

## Install

> Not published on PyPI. Install from GitHub.

### Option A — `uvx` (no install, recommended)

```bash
uvx --from "git+https://github.com/letsjustrun/fitness-mcp.git" fitness-mcp --help
```

### Option B — pipx (keep it on your PATH)

```bash
pipx install "git+https://github.com/letsjustrun/fitness-mcp.git"
fitness-mcp --help
```

### Option C — from source

```bash
git clone https://github.com/letsjustrun/fitness-mcp.git
cd fitness-mcp
uv venv --python 3.12
uv pip install -e ".[dev]"
.venv/bin/fitness-mcp --help
```

---

## Get a Garmin Personal API key

1. Sign in to [Garmin Connect](https://connect.garmin.com) on the web.
2. **Settings → Account → Personal API Token**.
3. Create a key. It looks like `GCDC_<uuid>.<uuid>.<base64>.<id>`.
4. Keep it private — treat it like a password.

> This is a per-user, read-only, own-data-only key. Garmin's Personal API does not support "sharing" or "delegation" — this project cannot use anyone else's data on your behalf and vice versa.

---

## Register with Claude Desktop

### Option 1 — DXT (one-click, recommended once released)

Download `fitness-mcp.dxt` from the [Releases page](#) and double-click. Claude Desktop will prompt for your Garmin key during install.

### Option 2 — manual config

Open **Settings → Developer → Edit Config** and add:

```json
{
  "mcpServers": {
    "fitness": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/letsjustrun/fitness-mcp.git",
        "fitness-mcp"
      ],
      "env": {
        "GARMIN_PERSONAL_API_KEY": "paste-your-key-here"
      }
    }
  }
}
```

Fully quit and relaunch Claude Desktop. Ask a new chat *"Using the fitness tools, show my last 3 nights of sleep."*

If you installed from source, replace `"command": "uvx", "args": ["fitness-mcp"]` with the absolute path to your venv's `fitness-mcp` script.

---

## Register with Claude Code

```bash
claude mcp add fitness \
  -e GARMIN_PERSONAL_API_KEY=your-key-here \
  -- uvx --from "git+https://github.com/letsjustrun/fitness-mcp.git" fitness-mcp
```

---

## Tools exposed

| Tool | Purpose |
|---|---|
| `get_activities(start, end, sport?, force_refresh?)` | Summary list of workouts in a date range |
| `get_activity_detail(activity_id)` | One activity — splits, HR zones, elevation profile if upstream exposes them |
| `get_sleep(start, end, force_refresh?)` | Per-night sleep: hours, deep/REM/light/awake, score |
| `get_daily_summary(start, end, force_refresh?)` | Daily wellness + sleep rollup |
| `get_trends(metric, start, end, bucket?)` | Aggregated time series: `resting_hr`, `steps`, `vo2max`, `hrv`, `sleep_score`, `training_load`, … |

Dates are `YYYY-MM-DD`. Full tool reference: [`docs/mcp-tools.md`](docs/mcp-tools.md).

---

## Running behind corporate TLS inspection (Zscaler, Netskope, …)

If your machine's HTTPS goes through a corporate proxy that re-signs certificates, Python won't trust the chain by default. Export the inspection root CA and point this server at it:

```bash
mkdir -p ~/.fitness_mcp
# macOS, Zscaler example:
security find-certificate -a -c "Zscaler" -p /Library/Keychains/System.keychain \
  > ~/.fitness_mcp/zscaler_ca.pem
CERTIFI=$(python -c 'import certifi; print(certifi.where())')
cat "$CERTIFI" ~/.fitness_mcp/zscaler_ca.pem > ~/.fitness_mcp/ca_bundle.pem
```

Then add `FITNESS_MCP_CA_BUNDLE=$HOME/.fitness_mcp/ca_bundle.pem` to your env (or the `env` block in your Claude Desktop config).

---

## Self-host over HTTP (multi-tenant)

HTTP mode is **multi-tenant and credential-free on the server**. Each user's `Authorization: Bearer <key>` *is* their Garmin Personal API Token. The server:

- extracts the key from the header per request
- uses it to call Garmin for that request only
- never stores any Garmin credentials
- isolates each user's SQLite cache rows via `sha256(key)[:16]`

Run it:

```bash
fitness-mcp --http --host 0.0.0.0 --port 8000
```

Clients connect to `http://your-host:8000/mcp` with their **own** Garmin key in the Authorization header. One Space / server can safely serve many users.

For public exposure, terminate TLS at a reverse proxy (cloudflared, Caddy, nginx). Full architecture notes in [`docs/architecture.md`](docs/architecture.md) and the Hugging Face Spaces deploy walkthrough in [`deploy/huggingface/DEPLOY.md`](deploy/huggingface/DEPLOY.md).

---

## Configuration reference

All settings are env vars (loaded from the process environment or `.env` in the working directory or `~/.fitness_mcp/.env`):

| Variable | Default | Purpose |
|---|---|---|
| `GARMIN_PERSONAL_API_KEY` | — | **Required in stdio mode.** In HTTP mode the key comes from the per-request Authorization header instead. |
| `FITNESS_MCP_TRANSPORT` | `stdio` | `stdio` or `http`. |
| `FITNESS_MCP_DB_PATH` | `~/.fitness_mcp/data.db` | SQLite cache location. |
| `FITNESS_MCP_LOG_LEVEL` | `INFO` | `DEBUG`/`INFO`/`WARNING`/`ERROR`. |
| `FITNESS_MCP_HTTP_TIMEOUT` | `30` | Per-request Garmin timeout, seconds. |
| `FITNESS_MCP_MAX_RANGE_DAYS` | `90` | Hard cap on tool-call date ranges. Clamped silently. |
| `FITNESS_MCP_CA_BUNDLE` | *(certifi default)* | Path to a custom CA bundle for TLS-inspected networks. |
| `FITNESS_MCP_HTTP_HOST` | `127.0.0.1` | HTTP bind host. |
| `FITNESS_MCP_HTTP_PORT` | `8000` | HTTP port. |
| `FITNESS_MCP_HTTP_PATH` | `/mcp` | HTTP mount path. |
| `FITNESS_MCP_HTTP_CORS_ORIGINS` | *(empty)* | Comma-separated origins for claude.ai web. |

---

## Development

```bash
uv venv --python 3.12
uv pip install -e ".[dev]"
.venv/bin/pytest                 # 26 unit tests, no network
.venv/bin/ruff check .           # lint
```

Tests stub the Garmin provider — no real API calls happen in CI.

Add a new provider? Walk-through: [`docs/adding-a-provider.md`](docs/adding-a-provider.md).

---

## Privacy

This server runs on your machine. Your Garmin data is cached to a SQLite file under your home directory. The author receives nothing, sees nothing, and keeps nothing.

If you self-host over HTTP, you become the data custodian — anyone with a valid bearer token can read your data. Keep tokens secret, keep TLS on, keep logs trimmed.

---

## License

MIT — see [`LICENSE`](LICENSE).

## Credits

- Built on the official [`garmin-connect-personal-api-python`](https://pypi.org/project/garmin-connect-personal-api-python/) client.
- MCP transport, routing, and schema generation by the official [MCP Python SDK](https://pypi.org/project/mcp/).
