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


def _start_zero_gpu_background_heartbeat(interval_seconds: int = 60) -> None:
    """Fire the @spaces.GPU heartbeat periodically in a background thread.

    Doing this inline on every HTTP request added 30–50 s of GPU-allocation
    latency per MCP call — Claude Desktop's SDK gave up at 30 s and dropped
    our tools from the session. A quiet background tick keeps the Zero GPU
    orchestrator satisfied without touching the request hot path.
    """
    if not _HAVE_SPACES:
        return

    import threading
    import time

    def _loop() -> None:
        # Touch once immediately so the first tick lands early.
        try:
            _zero_gpu_heartbeat()
        except Exception:
            pass
        while True:
            try:
                time.sleep(interval_seconds)
                _zero_gpu_heartbeat()
            except Exception:
                # A failed heartbeat shouldn't stop the loop.
                pass

    threading.Thread(target=_loop, name="zero-gpu-heartbeat", daemon=True).start()


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
    space_id = os.environ.get("SPACE_ID", "<owner>/<space>")
    owner, _, space = space_id.partition("/")
    host = f"{owner}-{space}.hf.space" if space else "<this-space>.hf.space"

    # When running on HF, auto-add our Space's public domain to the MCP
    # SDK's allowed-hosts list so its DNS-rebinding guard doesn't 421 every
    # request. Don't touch the setting if the deployer already configured it.
    if space and not os.environ.get("FITNESS_MCP_HTTP_ALLOWED_HOSTS"):
        os.environ["FITNESS_MCP_HTTP_ALLOWED_HOSTS"] = ",".join([
            host,
            f"{host}:443",
            "localhost",   # HF's internal probe uses localhost
            f"localhost:{os.environ.get('PORT', '7860')}",
            "127.0.0.1",
        ])

    settings = get_settings()
    mcp_asgi = build_asgi_app(create_app(), settings)
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

    # Mount at /x (Gradio owns /api/* for its own JSON-RPC routes).
    gradio_app.mount(MCP_MOUNT_PATH, mcp_asgi)

    # Keep Zero GPU happy with a periodic background tick — NOT in the
    # request path. Per-request @spaces.GPU calls added 30–50s of GPU
    # allocation latency per MCP call, which blew Claude Desktop's
    # 30 s request timeout.
    _start_zero_gpu_background_heartbeat(interval_seconds=60)

    port = int(os.environ.get("PORT", 7860))
    print(f"Running on local URL:  http://0.0.0.0:{port}", flush=True)
    print("To create a public link, set `share=True` in `launch()`.", flush=True)
    uvicorn.run(
        gradio_app, host="0.0.0.0", port=port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
