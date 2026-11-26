# Deploy fitness-mcp to Hugging Face Spaces (free tier)

Gradio SDK, free CPU basic hardware. ~10 min end-to-end. No credit card.

> Docker SDK is paywalled on HF's free tier as of Nov 2026. We work around that by using Gradio SDK as a thin wrapper — our `app.py` serves the real MCP server on port 7860 and adds a trivial Gradio landing page at `/ui` so the Space preview shows something.

---

## 1. Create the Space

1. Sign in to https://huggingface.co/.
2. Top-right **+** → **New Space**.
3. Fill in:
   - **Owner**: your HF username
   - **Space name**: `fitness-mcp`
   - **License**: MIT
   - **SDK**: **Gradio** → pick **Blank**
   - **Hardware**: **CPU basic — free**
   - **Visibility**: **Public** *(bearer token protects the data; private Spaces require HF Pro)*
4. Click **Create Space**.

---

## 2. Get an HF write token (for `git push`)

1. https://huggingface.co/settings/tokens
2. **Create new token** → type **Write** → name `fitness-mcp deploy` → copy `hf_...`.

---

## 3. Push the three files

The Space only needs three files — `app.py`, `requirements.txt`, and the HF-flavored `README.md`. The rest of the code (fitness_mcp package) is pulled from GitHub at build time via `requirements.txt`.

```bash
HF_USER=<your-hf-username>
SRC=/Users/harishsinghbisht/paytm/GarminMCP

# Clone the Space's git
git clone "https://huggingface.co/spaces/$HF_USER/fitness-mcp" /tmp/hf-fitness-mcp
cd /tmp/hf-fitness-mcp

# Copy only the three HF-specific files
cp "$SRC/deploy/huggingface/app.py"           ./app.py
cp "$SRC/deploy/huggingface/requirements.txt" ./requirements.txt
cp "$SRC/deploy/huggingface/README.md"        ./README.md

git add -A
git commit -m "Deploy fitness-mcp 0.1.0"
git push
# Username: your HF username
# Password: the hf_... write token from step 2
```

Space UI (https://huggingface.co/spaces/<you>/fitness-mcp) will show **Building…** for 2–4 minutes.

---

## 4. Set secrets

While it builds: Space UI → **Settings → Variables and secrets**.

| Name | Kind | Value |
|---|---|---|
| `GARMIN_PERSONAL_API_KEY` | **Secret** | your Garmin Personal API Token |
| `FITNESS_MCP_HTTP_BEARER_TOKENS` | **Secret** | `python -c 'import secrets; print(secrets.token_urlsafe(32))'` |
| `FITNESS_MCP_HTTP_CORS_ORIGINS` | **Variable** | `https://claude.ai` (only if you'll connect from claude.ai web / iPhone) |

Click **Restart Space** so the new secrets load. The server refuses to boot without `FITNESS_MCP_HTTP_BEARER_TOKENS` set — if you see "FATAL" in Space logs, this is why.

---

## 5. Verify

```bash
# Replace <you> with your HF username
curl -s https://<you>-fitness-mcp.hf.space/healthz
# -> {"status":"ok"}

curl -s -o /dev/null -w "%{http_code}\n" -X POST https://<you>-fitness-mcp.hf.space/mcp
# -> 401

curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}' \
  https://<you>-fitness-mcp.hf.space/mcp
# -> 200
```

The `/ui` page in the Space preview should also render a short markdown landing.

---

## 6. Register from a Claude client

### iPhone / iPad / claude.ai web

1. Settings → **Connectors** → **Add custom connector**.
2. URL: `https://<you>-fitness-mcp.hf.space/mcp`
3. Header: `Authorization: Bearer <your-token>`
4. Open a new chat, ask about your Garmin data.

### Claude Desktop (via `mcp-remote` shim)
See the HF Space README.

### Claude Code
```bash
claude mcp add --transport http fitness \
  "https://<you>-fitness-mcp.hf.space/mcp" \
  --header "Authorization: Bearer <your-token>"
```

---

## Updating

Repeat step 3 whenever you want to redeploy. HF rebuilds on every push.

Because `requirements.txt` pins `fitness-mcp @ git+https://github.com/letsjustrun/fitness-mcp.git@main`, every HF build pulls the latest `main`. For a frozen version, change `@main` to `@v0.1.0` (once you've tagged a release).

---

## Pausing / stopping

- Free tier Spaces pause themselves after 48h of no requests. First request after a nap wakes it in ~15s.
- Pause manually: Space UI → Settings → **Pause Space**.
- Delete: Settings → **Delete Space**.

## Known limitations of the free tier

- Ephemeral filesystem — cached Garmin data is wiped on redeploy / nap wake. Cache-aside re-syncs on the next tool call, so this is a latency hit, not a correctness problem.
- 16 GB RAM, 2 vCPU — plenty for this workload.
- No custom domain — `*.hf.space` only.
- One container; no horizontal scaling.

## If you upgrade to HF Pro and want Docker SDK

`deploy/huggingface/Dockerfile.alt` + `deploy/huggingface/.dockerignore.alt` are the Docker-SDK equivalent. Rename them to `Dockerfile` / `.dockerignore`, change `sdk: gradio` → `sdk: docker` in the Space's README front-matter, drop `app.py` and `requirements.txt`, and push.
