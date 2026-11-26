"""Hugging Face Space entry point — Gradio SDK free tier.

Multi-tenant HTTP server. No server-side secrets — each user supplies their
own Garmin Personal API key via `Authorization: Bearer <key>` on every
request. See the GitHub README for the full auth model.

HF's Gradio SDK probes port 7860 with Gradio-shaped requests and recycles
containers that don't answer them. To satisfy both HF and our MCP transport
we let Gradio build its own FastAPI (including `/`, `/info`, `/config`,
`/api/predict`, websocket, …), then mount the MCP Starlette app at `/api`.
Uvicorn launches that combined app.

Public routes:
    /               → Gradio landing (also what HF probes)
    /api/healthz    → MCP health
    /api/mcp        → MCP Streamable HTTP endpoint
"""
from __future__ import annotations

import os

import gradio as gr
import uvicorn
from gradio.routes import App as GradioApp

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
    landing.queue()  # HF's probe expects the Gradio queue to be running

    # Let Gradio build its own FastAPI app (gives HF everything it probes)
    # then layer our MCP ASGI onto it at /api.
    gradio_app = GradioApp.create_app(landing)
    gradio_app.mount(MCP_MOUNT_PATH, mcp_asgi)

    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(gradio_app, host="0.0.0.0", port=port, log_level=settings.log_level.lower())


if __name__ == "__main__":
    main()
