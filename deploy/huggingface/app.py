"""Hugging Face Space entry point — Gradio SDK free tier.

HF Spaces runs `python app.py` and routes HTTPS to whatever listens on port
7860. We don't actually use Gradio for anything — our product is an MCP
server. But HF's Gradio SDK expects a Gradio-shaped app, so we:

1. Build the real Streamable HTTP MCP app (`fitness_mcp.http_server.build_asgi_app`).
2. Mount a tiny Gradio landing at `/ui` just so the Space's UI preview shows
   something readable instead of an empty 404.
3. Run both under one uvicorn on 0.0.0.0:7860.

Secrets (GARMIN_PERSONAL_API_KEY, FITNESS_MCP_HTTP_BEARER_TOKENS) come from
the Space's Variables & secrets UI, injected as env vars.
"""
from __future__ import annotations

import os
import sys

import gradio as gr
import uvicorn
from fastapi import FastAPI

from fitness_mcp.config import get_settings
from fitness_mcp.http_server import build_asgi_app
from fitness_mcp.server import create_app


def _require_bearer_tokens(settings) -> None:
    """Safety: HF Spaces are publicly reachable. Refuse to boot without auth."""
    if not settings.bearer_token_set:
        print(
            "FATAL: FITNESS_MCP_HTTP_BEARER_TOKENS is not set. Hugging Face "
            "Spaces are reachable from the public internet; the server refuses "
            "to boot without a bearer token configured. Add the secret in "
            "Space Settings → Variables and secrets, then Restart the Space.",
            file=sys.stderr,
        )
        raise SystemExit(2)


def build_landing() -> gr.Blocks:
    with gr.Blocks(title="fitness-mcp", analytics_enabled=False) as demo:
        gr.Markdown(
            """
            # fitness-mcp 🏃

            A Streamable HTTP **Model Context Protocol** server that gives
            Claude read-only access to your Garmin Connect fitness data.

            ## Endpoints

            - `POST /mcp` — JSON-RPC over HTTP + SSE  (requires `Authorization: Bearer <token>`)
            - `GET /healthz` — public liveness probe

            ## Use from a Claude client

            Add as a Custom Connector with:

            - **URL** `https://<this-space>.hf.space/mcp`
            - **Header** `Authorization: Bearer <your token>`

            Full setup, config reference, and privacy notes:
            [github.com/letsjustrun/fitness-mcp](https://github.com/letsjustrun/fitness-mcp)
            """
        )
    return demo


def main() -> None:
    settings = get_settings()
    _require_bearer_tokens(settings)

    mcp_asgi = build_asgi_app(create_app(), settings)
    landing = build_landing()

    outer = FastAPI()
    outer = gr.mount_gradio_app(outer, landing, path="/ui")
    # mcp_asgi already has its own /mcp and /healthz routes. Mount at root so
    # Starlette forwards matching paths. Gradio's /ui mount registered first
    # takes precedence for /ui/* requests.
    outer.mount("/", mcp_asgi)

    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(outer, host="0.0.0.0", port=port, log_level=settings.log_level.lower())


if __name__ == "__main__":
    main()
