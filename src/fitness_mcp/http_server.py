"""Streamable HTTP transport.

Switch from stdio to HTTP by setting:
    FITNESS_MCP_TRANSPORT=http
    FITNESS_MCP_HTTP_HOST=0.0.0.0           # localhost by default
    FITNESS_MCP_HTTP_PORT=8000
    FITNESS_MCP_HTTP_BEARER_TOKENS=t1,t2    # required to bind off localhost
    FITNESS_MCP_HTTP_CORS_ORIGINS=https://claude.ai,https://*.anthropic.com

The server speaks MCP Streamable HTTP at `FITNESS_MCP_HTTP_PATH` (default `/mcp`)
and exposes a tiny `/healthz` for liveness checks.
"""
from __future__ import annotations

import logging

import uvicorn
from mcp.server.mcpserver import MCPServer
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from .config import Settings

log = logging.getLogger(__name__)


class BearerAuthMiddleware:
    """Minimal bearer-token gate.

    - Requests to `/healthz` pass through unauthenticated so load balancers work.
    - OPTIONS preflight passes through so CORS can negotiate.
    - Everything else must carry `Authorization: Bearer <t>` where `<t>` is in
      the configured allow-list.
    """

    def __init__(self, app: ASGIApp, tokens: set[str], protected_prefix: str) -> None:
        self._app = app
        self._tokens = tokens
        self._prefix = protected_prefix

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self._tokens:
            await self._app(scope, receive, send)
            return

        path: str = scope.get("path", "")
        method: str = scope.get("method", "GET")

        if method == "OPTIONS" or not path.startswith(self._prefix):
            await self._app(scope, receive, send)
            return

        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        auth = headers.get("authorization", "")
        if not auth.startswith("Bearer "):
            await self._reply(send, 401, "missing bearer token")
            return
        token = auth[len("Bearer ") :].strip()
        if token not in self._tokens:
            await self._reply(send, 403, "invalid bearer token")
            return
        await self._app(scope, receive, send)

    @staticmethod
    async def _reply(send: Send, status: int, msg: str) -> None:
        body = JSONResponse({"error": msg}, status_code=status)
        await body(scope={"type": "http"}, receive=None, send=send)  # type: ignore[arg-type]


async def _healthz(_request: Request) -> Response:
    return JSONResponse({"status": "ok"})


def build_asgi_app(mcp: MCPServer, settings: Settings) -> Starlette:
    """Attach auth + CORS + /healthz to the SDK's Streamable HTTP Starlette app.

    We mutate the SDK-provided app rather than mounting it under a parent,
    because mounted sub-apps don't receive Starlette lifespan events and the
    MCP session manager needs its lifespan to initialize its task group.
    """
    tokens = settings.bearer_token_set
    binding_off_localhost = settings.http_host not in {"127.0.0.1", "localhost", "::1"}

    if binding_off_localhost and not tokens:
        raise RuntimeError(
            f"Refusing to bind MCP HTTP on {settings.http_host} without "
            f"FITNESS_MCP_HTTP_BEARER_TOKENS. Set tokens or bind to 127.0.0.1."
        )

    app = mcp.streamable_http_app(
        streamable_http_path=settings.http_path,
        host=settings.http_host,
    )

    # Prepend /healthz so it wins before the MCP route matcher.
    app.router.routes.insert(0, Route("/healthz", _healthz, methods=["GET"]))

    # add_middleware wraps the existing ASGI stack, so order here is reverse:
    # the LAST add_middleware call becomes the OUTERMOST layer. We want:
    #   client -> CORS -> BearerAuth -> MCP app
    if tokens:
        app.add_middleware(
            BearerAuthMiddleware,
            tokens=tokens,
            protected_prefix=settings.http_path,
        )
    origins = settings.cors_origin_list
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "Mcp-Session-Id"],
            expose_headers=["Mcp-Session-Id"],
            allow_credentials=False,
        )
    return app


def serve_http(mcp: MCPServer, settings: Settings) -> None:
    app = build_asgi_app(mcp, settings)
    log.info(
        "fitness-mcp serving Streamable HTTP on http://%s:%d%s (auth=%s, cors=%d)",
        settings.http_host, settings.http_port, settings.http_path,
        "on" if settings.bearer_token_set else "OFF",
        len(settings.cors_origin_list),
    )
    uvicorn.run(
        app,
        host=settings.http_host,
        port=settings.http_port,
        log_level=settings.log_level.lower(),
        access_log=False,
    )
