---
title: fitness-mcp
emoji: 🏃
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
license: mit
short_description: MCP server exposing Garmin Connect fitness data (BYO key).
---

# fitness-mcp — Hugging Face Space

[GitHub](https://github.com/letsjustrun/fitness-mcp) · MIT

A Streamable HTTP **Model Context Protocol** server for reading your own Garmin Connect fitness data.

> This Space serves the MCP endpoint. The Gradio landing at `/ui` is just a readable page for the Space preview — the real product is the MCP endpoint at `/mcp`.

## Endpoint

```
https://<owner>-fitness-mcp.hf.space/mcp
```

All `/mcp` calls must send `Authorization: Bearer <token>` where `<token>` matches one in the Space secret `FITNESS_MCP_HTTP_BEARER_TOKENS`.

`GET /healthz` is public and returns `{"status":"ok"}`.

## Required Space secrets

Set these in **Settings → Variables and secrets** (do NOT bake them into the image):

| Name | Kind | What |
|---|---|---|
| `GARMIN_PERSONAL_API_KEY` | Secret | Garmin Connect → Settings → Account → Personal API Token. |
| `FITNESS_MCP_HTTP_BEARER_TOKENS` | Secret | Comma-separated list of bearer tokens you accept. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(32))"`. |
| `FITNESS_MCP_HTTP_CORS_ORIGINS` | Variable (optional) | Set to `https://claude.ai` to add as a Custom Connector in claude.ai web / iPhone. |

The server refuses to boot without `FITNESS_MCP_HTTP_BEARER_TOKENS` set — HF Spaces are public, so this is a hard requirement.

## Use from a Claude client

### iPhone / claude.ai web
Settings → **Connectors** → **Add custom connector**
- URL: `https://<owner>-fitness-mcp.hf.space/mcp`
- Header: `Authorization: Bearer <token>`

### Claude Desktop (via mcp-remote shim)
```json
{
  "mcpServers": {
    "fitness": {
      "command": "npx",
      "args": [
        "-y", "mcp-remote@latest",
        "https://<owner>-fitness-mcp.hf.space/mcp",
        "--header", "Authorization: Bearer ${AUTH_TOKEN}"
      ],
      "env": { "AUTH_TOKEN": "your-bearer-token" }
    }
  }
}
```

### Claude Code
```bash
claude mcp add --transport http fitness \
  "https://<owner>-fitness-mcp.hf.space/mcp" \
  --header "Authorization: Bearer <token>"
```

## Privacy

Code: public ([GitHub](https://github.com/letsjustrun/fitness-mcp)). Garmin data cached in `/tmp` inside the container — ephemeral, wiped on restart. Secrets live in HF's secret store and are only exposed to the running container as env vars.
