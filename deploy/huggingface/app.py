"""Hugging Face Space entry point (Gradio SDK, free tier).

Multi-tenant HTTP server. No server-side secrets — each user supplies their
own Garmin Personal API key via `Authorization: Bearer <key>` on every
request.

Public routes (port 7860):
    /               → Gradio landing (what HF's health probe hits)
    /x/healthz      → MCP health probe
    /x/mcp          → MCP Streamable HTTP endpoint
"""
# --------------------------------------------------------------------------
# Gradio 4.44's gradio.oauth does `from huggingface_hub import HfFolder`
# which was removed in huggingface_hub 0.26+. Pin in requirements.txt is
# ignored because pip refuses to downgrade pre-installed base packages.
# Stub HfFolder before any gradio import.
# --------------------------------------------------------------------------
import huggingface_hub as _hf_hub
if not hasattr(_hf_hub, "HfFolder"):
    class HfFolder:  # noqa: D401
        @staticmethod
        def get_token():
            return None

        @staticmethod
        def save_token(_token):  # pragma: no cover
            pass

        @staticmethod
        def delete_token():  # pragma: no cover
            pass
    _hf_hub.HfFolder = HfFolder


import contextlib
import os

import gradio as gr
import uvicorn
from gradio.routes import App as GradioApp

from fitness_mcp.config import get_settings
from fitness_mcp.http_server import build_asgi_app
from fitness_mcp.server import create_app

MCP_MOUNT_PATH = "/x"


# HF Zero GPU killswitch: orchestrator kills Spaces that don't declare at
# least one @spaces.GPU-decorated function with
# "No @spaces.GPU function detected during startup". We don't need a GPU —
# this decoy is never called.
try:
    import spaces  # type: ignore

    @spaces.GPU  # type: ignore[misc]
    def _zero_gpu_decoy():
        return "ok"
except ImportError:
    pass


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

    # Get Gradio's FastAPI without launching it ourselves — gives us the
    # chance to patch the lifespan context BEFORE uvicorn runs.
    gradio_app = GradioApp.create_app(landing)

    # Compose Gradio's own lifespan with our MCP app's lifespan. Mounting
    # mcp_asgi below would normally orphan its lifespan (Starlette doesn't
    # cascade to mounted sub-apps) and the MCP session manager's task group
    # never gets initialized — every request would crash with
    # "Task group is not initialized. Make sure to use run()."
    original_lifespan = gradio_app.router.lifespan_context

    @contextlib.asynccontextmanager
    async def combined_lifespan(app):
        async with mcp_asgi.router.lifespan_context(mcp_asgi):
            async with original_lifespan(app):
                yield

    gradio_app.router.lifespan_context = combined_lifespan

    # Mount MCP at /x (we moved off /api because Gradio reserves /api/*
    # for its own JSON-RPC routes).
    gradio_app.mount(MCP_MOUNT_PATH, mcp_asgi)

    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(
        gradio_app, host="0.0.0.0", port=port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
