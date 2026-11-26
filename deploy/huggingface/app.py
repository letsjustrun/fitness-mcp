"""Hugging Face Space entry point (Gradio SDK, Zero GPU free tier).

Multi-tenant HTTP server. No server-side secrets — each user supplies their
own Garmin Personal API key via `Authorization: Bearer <key>` on every
request.

Public routes (port 7860):
    /               → Gradio landing (what HF's health probe hits)
    /x/healthz      → MCP health probe
    /x/mcp          → MCP Streamable HTTP endpoint

Zero GPU quota: ~5 GPU-minutes/day for free accounts. The heartbeat below
consumes a tiny slice per MCP request — fine for ad-hoc iPhone testing,
not for sustained traffic. Move to CPU basic (requires a new Space) or
a different host (Render / tunnel) if you need always-on service.
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
from starlette.types import ASGIApp, Receive, Scope, Send

from fitness_mcp.config import get_settings
from fitness_mcp.http_server import build_asgi_app
from fitness_mcp.server import create_app

MCP_MOUNT_PATH = "/x"


# --------------------------------------------------------------------------
# HF Zero GPU heartbeat.
# --------------------------------------------------------------------------
# On Zero GPU hardware, the orchestrator reaps containers whose @spaces.GPU
# functions aren't actively invoked. Declaring one at startup isn't enough;
# it must be CALLED. We use a trivial decorated no-op and invoke it on every
# MCP request via middleware.
#
# When running on CPU basic (no `spaces` module) the import fails and the
# heartbeat is a no-op — the same app.py works on both hardware tiers.
# --------------------------------------------------------------------------
try:
    import spaces  # type: ignore

    @spaces.GPU  # type: ignore[misc]
    def _zero_gpu_heartbeat():
        """Touched on every MCP request. Does no real GPU work."""
        return "ok"

    _HAVE_SPACES = True
except ImportError:
    _HAVE_SPACES = False

    def _zero_gpu_heartbeat():
        return "ok"


class ZeroGPUHeartbeatMiddleware:
    """ASGI middleware that calls the @spaces.GPU-decorated heartbeat before
    passing the request through. No-op on CPU hardware (spaces not installed).
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if _HAVE_SPACES and scope["type"] == "http" and scope.get("method") != "OPTIONS":
            try:
                _zero_gpu_heartbeat()
            except Exception:
                # Never fail a user request because of the heartbeat.
                pass
        await self._app(scope, receive, send)


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

    # Get Gradio's FastAPI without launching uvicorn. Lets us patch the
    # lifespan to compose Gradio's startup/shutdown with the MCP server's
    # lifespan (the MCP session manager's task group gets initialized this
    # way; otherwise /x/mcp fails with "Task group is not initialized").
    gradio_app = GradioApp.create_app(landing)

    original_lifespan = gradio_app.router.lifespan_context

    @contextlib.asynccontextmanager
    async def combined_lifespan(app):
        async with mcp_asgi.router.lifespan_context(mcp_asgi):
            async with original_lifespan(app):
                yield

    gradio_app.router.lifespan_context = combined_lifespan

    # Keep Zero GPU happy: heartbeat the orchestrator on every request.
    gradio_app.add_middleware(ZeroGPUHeartbeatMiddleware)

    # Mount at /x (Gradio owns /api/* for its own JSON-RPC routes).
    gradio_app.mount(MCP_MOUNT_PATH, mcp_asgi)

    # Touch the heartbeat once at startup so Zero GPU allocates a slot
    # before the first user request arrives.
    try:
        _zero_gpu_heartbeat()
    except Exception:
        pass

    port = int(os.environ.get("PORT", 7860))
    print(f"Running on local URL:  http://0.0.0.0:{port}", flush=True)
    print("To create a public link, set `share=True` in `launch()`.", flush=True)
    uvicorn.run(
        gradio_app, host="0.0.0.0", port=port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
