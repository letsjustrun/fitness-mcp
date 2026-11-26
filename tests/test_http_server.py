"""Smoke tests for the HTTP transport.

The server auth model is per-request now: `Authorization: Bearer <garmin-key>`
is both the user's identity and their Garmin credential. There is no
server-side token allow-list.
"""
from __future__ import annotations

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
        FITNESS_MCP_HTTP_CORS_ORIGINS="",
    )
    base.update(overrides)
    return Settings(**{k.lower(): v for k, v in base.items()})


def test_healthz_is_public(tmp_db):
    app = build_asgi_app(create_app(), _settings())
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_mcp_path_requires_bearer_header(tmp_db):
    app = build_asgi_app(create_app(), _settings())
    with TestClient(app) as client:
        r = client.post("/mcp", json={"jsonrpc": "2.0", "method": "ping", "id": 1})
        assert r.status_code == 401
        assert "garmin" in r.json()["error"].lower()


def test_mcp_path_empty_bearer_rejected(tmp_db):
    app = build_asgi_app(create_app(), _settings())
    with TestClient(app) as client:
        r = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "ping", "id": 1},
            headers={"Authorization": "Bearer "},
        )
        assert r.status_code == 401


def test_mcp_path_accepts_any_bearer_token_shape(tmp_db):
    """The middleware extracts the key; validation happens at Garmin. We only
    assert that a well-formed Bearer header makes it past the gate."""
    app = build_asgi_app(create_app(), _settings())
    with TestClient(app) as client:
        r = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "ping", "id": 1},
            headers={"Authorization": "Bearer anything-nonempty"},
        )
        # Past the gate: whatever MCP returns is fine, just not 401/403.
        assert r.status_code not in (401, 403)
