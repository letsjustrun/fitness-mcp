# Deploy fitness-mcp to Render (free tier)

~5 minutes end-to-end. No credit card required for the free Web Service tier.

Why Render over HF Spaces: no GPU quota, no runtime shape requirements, clean Python buildpack. The one tradeoff is **the service spins down after 15 min of inactivity**; the first request after a nap takes ~30 s to boot. Subsequent requests are instant. Fine for ad-hoc iPhone / Desktop testing.

---

## 1. Sign up for Render

https://render.com/signup — connect with GitHub so Render can read `letsjustrun/fitness-mcp`. No card required for the free tier.

---

## 2. New Blueprint-based service

1. Render dashboard → **New +** → **Blueprint**.
2. Pick the GitHub repo `letsjustrun/fitness-mcp`.
3. Render detects `render.yaml` at the repo root and asks to deploy a web service named `fitness-mcp`.
4. Review the settings (nothing to change for the free tier):
   - Runtime: **Python 3.12**
   - Build command: `pip install -e .`
   - Start command: `fitness-mcp --http --host 0.0.0.0 --port $PORT`
   - Health check path: `/healthz`
   - Env vars: `FITNESS_MCP_LOG_LEVEL=INFO`, `FITNESS_MCP_HTTP_DISABLE_DNS_REBINDING=true`, `FITNESS_MCP_HTTP_CORS_ORIGINS=https://claude.ai`
   - Plan: **Free**
5. Click **Apply**.

Render queues the build. ~2 min for `pip install` + startup.

---

## 3. Grab the service URL

Once the status flips to **Live**, the service page shows a URL like:

```
https://fitness-mcp-<slug>.onrender.com
```

Verify from your terminal:

```bash
URL=https://fitness-mcp-<slug>.onrender.com

curl -s "$URL/healthz"
# -> {"status":"ok"}

curl -s -o /dev/null -w "%{http_code}\n" -X POST "$URL/mcp"
# -> 401  (missing bearer)

curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  -H "Authorization: Bearer <your-garmin-personal-api-token>" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}' \
  "$URL/mcp"
# -> 200
```

Note the MCP endpoint is `/mcp` on Render (not `/x/mcp` like the HF Space had — Render doesn't need the Gradio shell on top).

---

## 4. Register the connector in Claude

### iPhone / claude.ai web

Settings → Connectors → **Add custom connector**:
- URL: `https://fitness-mcp-<slug>.onrender.com/mcp`
- Header: `Authorization: Bearer <your-garmin-personal-api-token>`

### Claude Desktop (via `mcp-remote` shim, since org blocks UI)

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
"fitness": {
  "command": "/opt/homebrew/bin/npx",
  "args": [
    "-y", "mcp-remote@latest",
    "https://fitness-mcp-<slug>.onrender.com/mcp",
    "--header", "Authorization: Bearer ${GARMIN_KEY}"
  ],
  "env": { "GARMIN_KEY": "<your-garmin-personal-api-token>" }
}
```

Fully quit Claude Desktop (⌘Q) and reopen.

### Claude Code

```bash
claude mcp add --transport http fitness \
  "https://fitness-mcp-<slug>.onrender.com/mcp" \
  --header "Authorization: Bearer <your-garmin-personal-api-token>"
```

---

## 5. Updating

Push to GitHub `main` → Render auto-deploys. No manual rebuild. Logs tab in the Render dashboard shows build + runtime output.

---

## Known limitations of the free tier

- **Spin-down after 15 min idle.** First request after sleep wakes it in ~30 s. For continuous use, upgrade to the $7/mo Starter tier (always-on, no cold start).
- **No persistent disk.** SQLite cache rebuilds from Garmin on each cold start. Cache-aside sync handles this transparently — first call is slow, subsequent fast.
- **512 MB RAM, 0.1 CPU.** Fine for this workload.
- **One deploy per GitHub account on free tier.**

For a permanently-on hobby-grade service, Fly.io's Hobby plan ($5/mo) is the next step up.
