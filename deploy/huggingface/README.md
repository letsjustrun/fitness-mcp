---
title: fitness-mcp
emoji: 🏃
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 4.44.0
python_version: "3.12"
app_file: app.py
pinned: false
license: mit
short_description: Multi-tenant MCP server for Garmin Connect fitness data.
---

# fitness-mcp — Hugging Face Space

[GitHub](https://github.com/letsjustrun/fitness-mcp) · MIT

A Streamable HTTP **Model Context Protocol** server for reading Garmin Connect fitness data.

This Space is **multi-tenant and stateless on auth**: each user sends their *own* Garmin Personal API Token in the `Authorization` header. The Space stores no Garmin credentials — Garmin itself validates every call. SQLite cache rows are keyed by a hash of each user's key, so users never see each other's data.

## Endpoint

```
https://<owner>-fitness-mcp.hf.space/x/mcp
```

Every `/x/mcp` call must send:

```
Authorization: Bearer <your-garmin-personal-api-token>
```

Get your token in Garmin Connect web → **Settings → Account → Personal API Token**. Looks like `GCDC_<uuid>.<uuid>.<base64>.<id>`.

`GET /x/healthz` is public and returns `{"status":"ok"}`. The Space's landing (`/`) is a tiny Gradio page with the same instructions.

## Space variables

| Name | Kind | Needed? | What |
|---|---|---|---|
| `FITNESS_MCP_HTTP_CORS_ORIGINS` | Variable | Only for claude.ai web / iPhone | `https://claude.ai` |

**No `GARMIN_PERSONAL_API_KEY`, no `FITNESS_MCP_HTTP_BEARER_TOKENS`.** The Space holds no secrets.

## Add as a Claude Connector

### iPhone / claude.ai web
Settings → **Connectors → Add custom connector**
- URL: `https://<owner>-fitness-mcp.hf.space/x/mcp`
- Header: `Authorization: Bearer <your-garmin-personal-api-token>`

### Claude Desktop (via `mcp-remote` shim)
```json
{
  "mcpServers": {
    "fitness": {
      "command": "npx",
      "args": [
        "-y", "mcp-remote@latest",
        "https://<owner>-fitness-mcp.hf.space/x/mcp",
        "--header", "Authorization: Bearer ${GARMIN_KEY}"
      ],
      "env": { "GARMIN_KEY": "your-garmin-personal-api-token" }
    }
  }
}
```

### Claude Code
```bash
claude mcp add --transport http fitness \
  "https://<owner>-fitness-mcp.hf.space/x/mcp" \
  --header "Authorization: Bearer <your-garmin-personal-api-token>"
```

## Privacy

Code: public ([GitHub](https://github.com/letsjustrun/fitness-mcp)). The Space holds no Garmin credentials. Each user's Garmin key arrives on the HTTP wire, is used to call Garmin for that request, and is never written to disk by the Space. SQLite cache under `/tmp` keyed by `sha256(key)[:16]`; ephemeral and wiped between HF restarts.
