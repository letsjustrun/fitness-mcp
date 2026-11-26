"""Hugging Face Space entry point — Gradio SDK free tier.

Multi-tenant HTTP server. No server-side secrets — each user supplies their
own Garmin Personal API key via `Authorization: Bearer <key>` on every
request. See the GitHub README for the full auth model.

Public routes (served on port 7860):
    /               → Gradio landing page (what HF's health probe hits)
    /api/healthz    → MCP health probe
    /api/mcp        → MCP Streamable HTTP endpoint

We let `demo.launch()` own the uvicorn (HF's Gradio SDK expects exactly this
shape — queue, websocket, /info, /config, static files — nothing we want to
reimplement). Once it's running we mount the MCP ASGI onto `demo.app` so
`/api/*` is served by the same uvicorn.
"""
from __future__ import annotations

import os
import threading

import gradio as gr

from fitness_mcp.config import get_settings
from fitness_mcp.http_server import build_asgi_app
from fitness_mcp.server import create_app

MCP_MOUNT_PATH = "/api"


def build_landing(public_mcp_url_hint: str) -> gr.Blocks:
    with gr.Blocks(title="fitness-mcp", analytics_enabled=False) as demo:
        gr.Markdown(
            f"""
            # fitness-mcp 🏃

            A **Streamable HTTP Model Context Protocol** server that gives
            Claude read-only access to your Garmin Connect fitness data.

            ## Multi-tenant — bring your own Garmin key

            This Space stores no Garmin credentials. Every request must
            carry *your own* Garmin Personal API Token in the Authorization
            header. SQLite cache rows are keyed by the hash of your key.

            ## Add as a Claude Connector

            - **URL**: `{public_mcp_url_hint}`
            - **Authorization**: `Bearer <your-garmin-personal-api-key>`

            Get your key from Garmin Connect → Settings → Account →
            Personal API Token.

            ## Also

            - `GET {MCP_MOUNT_PATH}/healthz` — public liveness probe
            - Source + full docs on
              [GitHub](https://github.com/letsjustrun/fitness-mcp).
            """
        )
    return demo


def main() -> None:
    settings = get_settings()
    mcp_asgi = build_asgi_app(create_app(), settings)

    space_id = os.environ.get("SPACE_ID", "<owner>/<space>")
    owner, _, space = space_id.partition("/")
    host = f"{owner}-{space}.hf.space" if space else "<this-space>.hf.space"
    public_mcp_url = f"https://{host}{MCP_MOUNT_PATH}{settings.http_path}"

    landing = build_landing(public_mcp_url)
    landing.queue()

    port = int(os.environ.get("PORT", 7860))
    # prevent_thread_lock=True returns immediately once uvicorn is bound,
    # so we can keep configuring landing.app before entering the forever wait.
    landing.launch(
        server_name="0.0.0.0",
        server_port=port,
        prevent_thread_lock=True,
        inbrowser=False,
        quiet=False,
        show_api=False,
    )
    # landing.app is the FastAPI instance uvicorn is now serving. Starlette
    # mounts are consulted per-request, so adding this after launch is fine.
    landing.app.mount(MCP_MOUNT_PATH, mcp_asgi)
    # Block the main thread forever so the Python process stays alive.
    threading.Event().wait()


if __name__ == "__main__":
    main()
