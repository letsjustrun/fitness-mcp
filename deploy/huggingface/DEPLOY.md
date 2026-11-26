# Deploy fitness-mcp to Hugging Face Spaces (free tier, multi-tenant)

Gradio SDK, free CPU hardware. ~10 min end-to-end.

> This deploy is **multi-tenant and stateless on auth** — the Space holds no Garmin credentials. Each user supplies their own Garmin Personal API Token in the Claude Connector's `Authorization` header. Nobody can read anybody else's data.

---

## 1. Create the Space

1. Sign in to https://huggingface.co/.
2. Top-right **+** → **New Space**.
3. Fill in:
   - **Owner**: your HF username
   - **Space name**: `fitness-mcp`
   - **License**: MIT
   - **SDK**: **Gradio** → pick **Blank**
   - **Hardware**: **CPU basic — free** (Zero GPU `zero-a10g` also works; both free)
   - **Visibility**: **Public**
4. Click **Create Space**.

---

## 2. Get an HF write token (for `git push`)

https://huggingface.co/settings/tokens → **Create new token** → type **Write** → name `fitness-mcp deploy` → copy `hf_...`.

---

## 3. Push the three files

The Space only needs three files — `app.py`, `requirements.txt`, and the HF-flavored `README.md`. The `fitness_mcp` package is pulled from GitHub at build time via `requirements.txt`.

```bash
HF_USER=<your-hf-username>
SRC=/Users/harishsinghbisht/paytm/GarminMCP

# Clone the empty Space's git
git clone "https://huggingface.co/spaces/$HF_USER/fitness-mcp" /tmp/hf-fitness-mcp
cd /tmp/hf-fitness-mcp

# Copy only the three HF-specific files
cp "$SRC/deploy/huggingface/app.py"           ./app.py
cp "$SRC/deploy/huggingface/requirements.txt" ./requirements.txt
cp "$SRC/deploy/huggingface/README.md"        ./README.md

git add -A
git commit -m "Deploy fitness-mcp 0.1.0 (multi-tenant)"
git push
# Username: your HF username
# Password: the hf_... write token from step 2
```

Space UI (https://huggingface.co/spaces/<you>/fitness-mcp) will show **Building…** for 2–4 minutes.

---

## 4. Set the ONE variable (optional)

Only needed if you'll connect from claude.ai web or iPhone — their browser/app needs CORS to be configured.

Space UI → **Settings → Variables and secrets** → **New variable**:

| Name | Kind | Value |
|---|---|---|
| `FITNESS_MCP_HTTP_CORS_ORIGINS` | **Variable** | `https://claude.ai` |

**No `GARMIN_PERSONAL_API_KEY`, no server-side bearer tokens.** The Space is designed to be credential-free.

Click **Restart Space** after setting the variable so it takes effect.

---

## 5. Verify

```bash
# Replace <you> with your HF username
curl -s https://<you>-fitness-mcp.hf.space/healthz
# -> {"status":"ok"}

curl -s -o /dev/null -w "%{http_code}\n" -X POST https://<you>-fitness-mcp.hf.space/mcp
# -> 401  (missing bearer header)

curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  -H "Authorization: Bearer <your-garmin-personal-api-token>" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}' \
  https://<you>-fitness-mcp.hf.space/mcp
# -> 200
```

The `/ui` page in the Space preview should render a short landing with instructions users can share.

---

## 6. Register from a Claude client

### iPhone / iPad / claude.ai web
1. Settings → **Connectors** → **Add custom connector**.
2. URL: `https://<you>-fitness-mcp.hf.space/mcp`
3. Header: `Authorization: Bearer <your-garmin-personal-api-token>`
4. Open a new chat, ask about your Garmin data.

### Claude Desktop (via `mcp-remote` shim)
See the HF Space README.

### Claude Code
```bash
claude mcp add --transport http fitness \
  "https://<you>-fitness-mcp.hf.space/mcp" \
  --header "Authorization: Bearer <your-garmin-personal-api-token>"
```

---

## Sharing the Space with other users

Just give them the URL + instructions. They:

1. Create their own Garmin Personal API Token in **their own** Garmin Connect account.
2. Add the Space as a Claude Connector using **their** token in the Authorization header.
3. See **their own** fitness data — your data (and everyone else's) stays invisible to them.

No HF account, no signup form, no coordination needed.

---

## Updating

Repeat step 3 whenever you want to redeploy. HF rebuilds on every push. Because `requirements.txt` pins `fitness-mcp @ git+https://github.com/letsjustrun/fitness-mcp.git@main`, every HF build pulls the latest `main`. For a frozen version, change `@main` to `@v0.1.0` (once you've tagged a release).

## Known limitations of the free tier

- Ephemeral filesystem — cached data is wiped on redeploy / nap wake. Cache-aside re-syncs on the next tool call, so this is a latency hit, not a correctness problem.
- 16 GB RAM, 2 vCPU — plenty for this workload.
- Memory grows with distinct users; the Garmin provider cache holds one instance per tenant. Restart the Space to free it.
- No custom domain — `*.hf.space` only.
- One container; no horizontal scaling.
