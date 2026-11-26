"""Smoke tests for the HTTP transport wrapping.

We don't exercise the full MCP JSON-RPC — that belongs in an end-to-end test
against a live client. These assertions pin down the auth gate, the health
check, and the "refuse to bind off localhost without tokens" safety.
"""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from fitness_mcp.config import Settings
from fitness_mcp.http_server import build_asgi_app
from fitness_mcp.server import create_app


def _settings(**overrides) -> Settings:
    base = dict(
        FITNESS_MCP_TRANSPORT="http",
        FITNESS_MCP_HTTP_HOST="127.0.0.1",
        FITNESS_MCP_HTTP_PORT=8000,
        FITNESS_MCP_HTTP_PATH="/mcp",
        FITNESS_MCP_HTTP_BEARER_TOKENS="",
        FITNESS_MCP_HTTP_CORS_ORIGINS="",
    )
    base.update(overrides)
    return Settings(**{k.lower(): v for k, v in base.items()})


def test_refuses_to_bind_off_localhost_without_tokens(tmp_db):
    mcp = create_app()
    s = _settings(FITNESS_MCP_HTTP_HOST="0.0.0.0")
    with pytest.raises(RuntimeError, match="Refusing to bind"):
        build_asgi_app(mcp, s)


def test_healthz_is_public(tmp_db):
    mcp = create_app()
    s = _settings(FITNESS_MCP_HTTP_BEARER_TOKENS="sekret")
    app = build_asgi_app(mcp, s)
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_mcp_path_requires_bearer_when_tokens_set(tmp_db):
    mcp = create_app()
    s = _settings(FITNESS_MCP_HTTP_BEARER_TOKENS="good-token")
    app = build_asgi_app(mcp, s)
    # Context-manager form runs Starlette lifespan events so the SDK's task
    # group is initialized before any request is dispatched.
    with TestClient(app) as client:
        r = client.post("/mcp", json={"jsonrpc": "2.0", "method": "ping", "id": 1})
        assert r.status_code == 401

        r = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "ping", "id": 1},
            headers={"Authorization": "Bearer nope"},
        )
        assert r.status_code == 403

        r = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "ping", "id": 1},
            headers={"Authorization": "Bearer good-token"},
        )
        assert r.status_code not in (401, 403)


def test_mcp_path_open_when_no_tokens_configured(tmp_db):
    """With no tokens we're localhost-only; the gate must not block anything."""
    mcp = create_app()
    s = _settings()
    app = build_asgi_app(mcp, s)
    with TestClient(app) as client:
        r = client.post("/mcp", json={"jsonrpc": "2.0", "method": "ping", "id": 1})
        assert r.status_code not in (401, 403)
