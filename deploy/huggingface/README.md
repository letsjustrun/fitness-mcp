---
title: fitness-mcp
emoji: 🏃
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: MCP server exposing Garmin Connect fitness data (BYO key).
---

# fitness-mcp — Hugging Face Space

[GitHub](https://github.com/letsjustrun/fitness-mcp) · MIT-licensed

A Streamable HTTP Model Context Protocol server that gives Claude read-only access to your own Garmin Connect data (activities, sleep, HRV, VO2 max, body battery, trends).

## Endpoint

```
https://<owner>-fitness-mcp.hf.space/mcp
```

All requests must send `Authorization: Bearer <token>` where `<token>` matches one in `FITNESS_MCP_HTTP_BEARER_TOKENS`.

`GET /healthz` is public and returns `{"status":"ok"}`.

## Required Space secrets

Set these in **Space Settings → Variables and secrets** (do NOT bake them into the image):

| Name | Kind | What |
|---|---|---|
| `GARMIN_PERSONAL_API_KEY` | secret | Your Garmin Connect Personal API Token (Settings → Account → Personal API Token in Garmin Connect web). |
| `FITNESS_MCP_HTTP_BEARER_TOKENS` | secret | Comma-separated list of bearer tokens you accept. Generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`. |
| `FITNESS_MCP_HTTP_CORS_ORIGINS` | variable (optional) | Set to `https://claude.ai` if you want to add this as a Custom Connector in claude.ai web / iOS. |

## Use from Claude

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

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

### claude.ai web / iPhone

Settings → Connectors → **Add custom connector**.

| Field | Value |
|---|---|
| URL | `https://<owner>-fitness-mcp.hf.space/mcp` |
| Header | `Authorization: Bearer <your-token>` |

## Privacy

All code is in [GitHub](https://github.com/letsjustrun/fitness-mcp). The Space runs it as-is. Your Garmin data is cached in `/tmp` inside the container — ephemeral. Secrets stay in HF's secret store.
