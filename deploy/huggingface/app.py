"""Hugging Face Space entry point — Gradio SDK free tier.

Multi-tenant HTTP server. No server-side secrets — each user supplies their
own Garmin Personal API key via `Authorization: Bearer <key>` in the Claude
Connector config. See the GitHub README for the full auth model.

HF Gradio Spaces run `python app.py` and expect something on port 7860. We
serve the real MCP endpoints (/mcp + /healthz) and mount a trivial Gradio
landing at /ui so the Space's preview isn't empty.
"""
from __future__ import annotations

import os

import gradio as gr
import uvicorn
from fastapi import FastAPI

from fitness_mcp.config import get_settings
from fitness_mcp.http_server import build_asgi_app
from fitness_mcp.server import create_app


def build_landing() -> gr.Blocks:
    with gr.Blocks(title="fitness-mcp", analytics_enabled=False) as demo:
        gr.Markdown(
            """
            # fitness-mcp 🏃

            A **Streamable HTTP Model Context Protocol** server that gives
            Claude read-only access to Garmin Connect fitness data.

            ## Multi-tenant — bring your own Garmin key

            This Space does not store any Garmin credentials. Every request
            must carry **your own** Garmin Personal API Token in the
            `Authorization` header. Your data lives in a cache row keyed by
            the hash of your key — nobody else using this Space can read it.

            ## Endpoints

            - `POST /mcp` — JSON-RPC over HTTP + SSE (auth required)
            - `GET /healthz` — public liveness probe

            ## Add as a Claude Connector

            - **URL**: `https://<this-space>.hf.space/mcp`
            - **Authorization**: `Bearer <your-garmin-personal-api-key>`

            Get the key from Garmin Connect web → Settings → Account →
            Personal API Token.

            Full setup, privacy notes, and Claude Desktop / Code instructions
            on GitHub:
            [github.com/letsjustrun/fitness-mcp](https://github.com/letsjustrun/fitness-mcp).
            """
        )
    return demo


def main() -> None:
    settings = get_settings()
    mcp_asgi = build_asgi_app(create_app(), settings)
    landing = build_landing()

    outer = FastAPI()
    outer = gr.mount_gradio_app(outer, landing, path="/ui")
    # mcp_asgi already serves /mcp and /healthz; mount at root to forward
    # them. Gradio's /ui mount (registered first) wins for /ui/* paths.
    outer.mount("/", mcp_asgi)

    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(outer, host="0.0.0.0", port=port, log_level=settings.log_level.lower())


if __name__ == "__main__":
    main()
