"""Hugging Face Space entry point.

Gradio SDK insists on having a Gradio app but every combination we tried
(gr.mount_gradio_app, gradio.routes.App.create_app, demo.launch with
prevent_thread_lock) hit a different Gradio/Jinja/huggingface_hub issue.
The Space only needs *something* to listen on port 7860; HF's "is this
Space alive" check is a TCP-level readiness probe, not a Gradio API probe.

So we drop Gradio entirely and serve:

    /               → tiny static HTML landing (keeps HF's Space preview happy)
    /api/healthz    → MCP health probe
    /api/mcp        → MCP Streamable HTTP endpoint

Everything runs under one uvicorn on 0.0.0.0:7860.

Multi-tenant: no server-side secrets. Each user sends their own Garmin
Personal API key via `Authorization: Bearer <key>` on every request.
See https://github.com/letsjustrun/fitness-mcp for the full auth model.
"""
from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from fitness_mcp.config import get_settings
from fitness_mcp.http_server import build_asgi_app
from fitness_mcp.server import create_app

MCP_MOUNT_PATH = "/api"


_LANDING_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>fitness-mcp</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
            sans-serif; max-width: 680px; margin: 3em auto; padding: 0 1em;
            color: #222; line-height: 1.55; }}
    h1 {{ margin-bottom: 0; }}
    code {{ background: #f3f3f3; padding: 2px 4px; border-radius: 3px; }}
    pre {{ background: #f3f3f3; padding: 1em; border-radius: 6px;
            overflow-x: auto; }}
    .muted {{ color: #777; font-size: 0.9em; }}
  </style>
</head>
<body>
  <h1>fitness-mcp 🏃</h1>
  <p class="muted">A Streamable HTTP MCP server for Garmin Connect fitness data.</p>

  <h2>Multi-tenant — bring your own Garmin key</h2>
  <p>This Space stores no Garmin credentials. Every request must carry
  <em>your own</em> Garmin Personal API Token in the <code>Authorization</code>
  header. SQLite cache rows are keyed by the hash of your key, so nobody
  else can read your data.</p>

  <h2>Add as a Claude Connector</h2>
  <pre>URL     : {public_mcp_url}
Header  : Authorization: Bearer &lt;your-garmin-personal-api-token&gt;</pre>
  <p>Get your key at <a href="https://connect.garmin.com">Garmin Connect</a>
  → Settings → Account → Personal API Token.</p>

  <h2>Also</h2>
  <ul>
    <li><code>GET {mcp_path}/healthz</code> — public liveness probe</li>
    <li>Source + full docs on
      <a href="https://github.com/letsjustrun/fitness-mcp">GitHub</a></li>
  </ul>
</body>
</html>
"""


def main() -> None:
    settings = get_settings()
    mcp_asgi = build_asgi_app(create_app(), settings)

    space_id = os.environ.get("SPACE_ID", "<owner>/<space>")
    owner, _, space = space_id.partition("/")
    host = f"{owner}-{space}.hf.space" if space else "<this-space>.hf.space"
    public_mcp_url = f"https://{host}{MCP_MOUNT_PATH}{settings.http_path}"

    app = FastAPI(docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def landing() -> str:
        return _LANDING_TEMPLATE.format(
            public_mcp_url=public_mcp_url,
            mcp_path=MCP_MOUNT_PATH,
        )

    app.mount(MCP_MOUNT_PATH, mcp_asgi)

    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level=settings.log_level.lower())


if __name__ == "__main__":
    main()
