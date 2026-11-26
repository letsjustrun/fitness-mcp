"""Streamable HTTP transport.

Multi-tenant auth model (see auth.py):

- Every `/mcp` request carries `Authorization: Bearer <garmin-personal-api-key>`.
- The user's own Garmin Personal API Token IS the auth credential.
- The server stores NO Garmin credentials — it pulls the key out of each
  request, uses it to talk to Garmin, and lets Garmin do the actual
  validation. If the key is wrong, the user's Garmin fetch errors; no
  separate server-side auth table is needed.
- SQLite rows and the Garmin bearer-token cache are keyed by a short
  hash of the key (tenant_id), so users never see each other's data.

Switch from stdio to HTTP by setting FITNESS_MCP_TRANSPORT=http
(or by passing `--http` on the CLI).
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

from .auth import current_garmin_key, current_tenant_id, tenant_id_from_key
from .config import Settings

log = logging.getLogger(__name__)


class GarminKeyMiddleware:
    """Pulls the user's Garmin Personal API key out of each request's
    Authorization header and publishes it on the auth context vars for the
    duration of the request.

    - `GET /healthz` passes through unauthenticated for load balancers.
    - `OPTIONS` passes through so CORS preflight succeeds.
    - Any other request to the MCP path with a missing or malformed
      Authorization header returns 401.
    """

    def __init__(self, app: ASGIApp, protected_prefix: str) -> None:
        self._app = app
        self._prefix = protected_prefix

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
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
            await self._reply(send, 401,
                              "Missing Authorization header. "
                              "Send 'Authorization: Bearer <your-garmin-personal-api-key>'.")
            return
        key = auth[len("Bearer ") :].strip()
        if not key:
            await self._reply(send, 401, "Empty bearer token.")
            return

        key_token = current_garmin_key.set(key)
        tenant_token = current_tenant_id.set(tenant_id_from_key(key))
        try:
            await self._app(scope, receive, send)
        finally:
            current_garmin_key.reset(key_token)
            current_tenant_id.reset(tenant_token)

    @staticmethod
    async def _reply(send: Send, status: int, msg: str) -> None:
        body = JSONResponse({"error": msg}, status_code=status)
        await body(scope={"type": "http"}, receive=None, send=send)  # type: ignore[arg-type]


async def _healthz(_request: Request) -> Response:
    return JSONResponse({"status": "ok"})


def build_asgi_app(mcp: MCPServer, settings: Settings) -> Starlette:
    """Attach the Garmin-key middleware, optional CORS, and /healthz to the
    SDK's Streamable HTTP Starlette app.

    We mutate the SDK-provided app rather than mounting it, because Starlette
    does not cascade lifespan events to mounted sub-apps and the MCP session
    manager relies on its lifespan to initialize.
    """
    app = mcp.streamable_http_app(
        streamable_http_path=settings.http_path,
        host=settings.http_host,
    )

    # Prepend /healthz so it wins before the MCP matcher sees the request.
    app.router.routes.insert(0, Route("/healthz", _healthz, methods=["GET"]))

    # add_middleware wraps the ASGI stack — last call becomes OUTERMOST. We
    # want:  client -> CORS -> GarminKeyMiddleware -> MCP app
    app.add_middleware(GarminKeyMiddleware, protected_prefix=settings.http_path)
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
        "fitness-mcp serving Streamable HTTP on http://%s:%d%s "
        "(auth=per-request Garmin key, cors=%d origins)",
        settings.http_host, settings.http_port, settings.http_path,
        len(settings.cors_origin_list),
    )
    uvicorn.run(
        app,
        host=settings.http_host,
        port=settings.http_port,
        log_level=settings.log_level.lower(),
        access_log=False,
    )
