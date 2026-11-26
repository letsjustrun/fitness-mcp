# Deploy fitness-mcp to Hugging Face Spaces

~15 minutes end-to-end. No credit card, no cost on the free CPU tier.

---

## 1. Create the Space

1. Sign in at https://huggingface.co/ (free account).
2. Top-right **+** menu → **New Space**.
3. Fill in:
   - **Owner**: your HF username
   - **Space name**: `fitness-mcp`
   - **License**: MIT
   - **SDK**: **Docker** → pick **Blank** (we ship our own Dockerfile)
   - **Hardware**: **CPU basic — free**
   - **Visibility**: **Public** *(the bearer token protects the data; private Spaces require HF Pro)*
4. Click **Create Space**.
5. Note the Space's git URL — it'll look like `https://huggingface.co/spaces/<you>/fitness-mcp`.

---

## 2. Get an HF access token (for `git push` auth)

1. https://huggingface.co/settings/tokens
2. **Create new token** → type: **Write**, name: `fitness-mcp deploy`.
3. Copy the `hf_...` token.

---

## 3. Push the code

From your checkout of **this** repo (adjust paths if yours is elsewhere):

```bash
HF_USER=<your-hf-username>
SRC=/Users/harishsinghbisht/paytm/GarminMCP

# Clone the empty Space's git repo
git clone "https://huggingface.co/spaces/$HF_USER/fitness-mcp" /tmp/hf-fitness-mcp
cd /tmp/hf-fitness-mcp

# Sync our project in. We exclude .git, venv, caches, tests, dxt — the Space
# only needs the runtime image, not the dev harness.
rsync -a --delete \
  --exclude='.git/' --exclude='.venv/' --exclude='dist/' \
  --exclude='tests/' --exclude='docs/' --exclude='.github/' \
  --exclude='dxt/' --exclude='CLAUDE.md' --exclude='.env' --exclude='.env.*' \
  --exclude='README.md' \
  "$SRC/" ./

# Use the HF-flavored README (has the required front-matter)
cp "$SRC/deploy/huggingface/README.md" ./README.md

git add -A
git commit -m "Deploy fitness-mcp 0.1.0"
git push
# Username: your HF username
# Password: the hf_... token from step 2
```

The Space UI (https://huggingface.co/spaces/<you>/fitness-mcp) will show **Building…**. Builds take 2–4 minutes on the free tier.

---

## 4. Set secrets

While it builds: in the Space UI → **Settings** → **Variables and secrets**:

| Name | Kind | Value |
|---|---|---|
| `GARMIN_PERSONAL_API_KEY` | **Secret** | your Garmin Personal API Token |
| `FITNESS_MCP_HTTP_BEARER_TOKENS` | **Secret** | `python -c 'import secrets; print(secrets.token_urlsafe(32))'` |
| `FITNESS_MCP_HTTP_CORS_ORIGINS` | **Variable** | `https://claude.ai` (only if you'll connect from claude.ai web / iPhone) |

Click **Restart** after setting secrets so the new values take effect.

---

## 5. Verify

```bash
# Replace <you> with your HF username
curl -s https://<you>-fitness-mcp.hf.space/healthz
# -> {"status":"ok"}

# Auth sanity check
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  https://<you>-fitness-mcp.hf.space/mcp
# -> 401

curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}' \
  https://<you>-fitness-mcp.hf.space/mcp
# -> 200
```

If both match, you're live.

---

## 6. Register from a Claude client

### iPhone / iPad / claude.ai web

1. Settings → **Connectors** → **Add custom connector**.
2. URL: `https://<you>-fitness-mcp.hf.space/mcp`
3. Header: `Authorization: Bearer <your-token>`
4. Open a new chat, ask about your Garmin data.

### Claude Desktop (via `mcp-remote` shim)

See the HF Space README (deploy/huggingface/README.md).

### Claude Code

```bash
claude mcp add --transport http fitness \
  "https://<you>-fitness-mcp.hf.space/mcp" \
  --header "Authorization: Bearer <your-token>"
```

---

## Updating

Repeat step 3 whenever you want to redeploy. HF rebuilds on every push.

## Pausing / stopping

- Spaces pause themselves after 48h of no requests. First request after a nap wakes it in ~15s.
- To pause manually: Space UI → Settings → **Pause Space** (stops billing-like counters even though it's free).
- To delete: Settings → **Delete Space**.

## Known limitations of the free tier

- Ephemeral filesystem — cached Garmin data is wiped on redeploy / nap wake.
  Cache-aside re-syncs on the next tool call, so this is a latency hit, not a correctness problem.
- No custom domain — you get `*.hf.space`.
- One container instance; no horizontal scaling.
- Request logs retention is limited.

For long-term hosting, graduate to Fly.io / Render / a tiny VM once the POC proves itself.
