"""Hugging Face Space entry point (Gradio SDK, CPU basic free tier).

Multi-tenant HTTP server. No server-side secrets — each user supplies their
own Garmin Personal API key via `Authorization: Bearer <key>` on every
request.

Public routes (all on port 7860):
    /               → tiny Gradio landing (what HF's health probe hits)
    /api/healthz    → MCP health probe
    /api/mcp        → MCP Streamable HTTP endpoint

Important: this Space must run on **CPU basic**, not Zero GPU. Zero GPU
expects at least one `@spaces.GPU`-decorated function and kills the
container if it doesn't find one.
"""
# --------------------------------------------------------------------------
# HF's Gradio SDK free-tier image ships huggingface_hub >= 0.26, but
# Gradio 4.44's gradio.oauth does `from huggingface_hub import HfFolder`
# which was removed in 0.26+. Our huggingface_hub<0.26 pin in requirements
# is ignored because pip won't downgrade already-installed packages without
# --force-reinstall. Stub HfFolder onto the module before any gradio import.
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

import os
import threading

import gradio as gr

from fitness_mcp.config import get_settings
from fitness_mcp.http_server import build_asgi_app
from fitness_mcp.server import create_app

MCP_MOUNT_PATH = "/api"


# HF Zero GPU killswitch: the orchestrator kills Spaces that don't declare at
# least one @spaces.GPU-decorated function on startup with
# "No @spaces.GPU function detected during startup". We don't actually need
# a GPU — this stub is never called. Only runs when the `spaces` module is
# importable (which it is in the HF container).
try:
    import spaces  # type: ignore

    @spaces.GPU  # type: ignore[misc]
    def _zero_gpu_decoy():
        """Decoy so HF Zero GPU orchestrator keeps the container alive."""
        return "ok"
except ImportError:
    # Running locally; no `spaces` package. Nothing to do.
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

    port = int(os.environ.get("PORT", 7860))
    # prevent_thread_lock returns once uvicorn is bound; we then mount our
    # MCP ASGI onto landing.app. Starlette looks up mounts per-request so
    # late registration is fine.
    landing.launch(
        server_name="0.0.0.0",
        server_port=port,
        prevent_thread_lock=True,
        inbrowser=False,
        show_api=False,
        quiet=False,
    )
    landing.app.mount(MCP_MOUNT_PATH, mcp_asgi)
    threading.Event().wait()


if __name__ == "__main__":
    main()
