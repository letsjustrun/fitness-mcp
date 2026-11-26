"""Per-request Garmin credential propagation.

HTTP transport: the user's Garmin Personal API key arrives on every request
as `Authorization: Bearer <key>`. The ASGI middleware in `http_server.py`
pulls it out and stores it in these context vars. Tools and the provider
factory read from here — they never see the raw request.

Tenant identity is a non-reversible hash of the key so we can use it as a
SQLite row key, a cache lookup, and in log lines without ever surfacing the
raw credential.

Stdio transport (local single-user install) leaves these unset and falls
back to `GARMIN_PERSONAL_API_KEY` from env.
"""
from __future__ import annotations

import hashlib
from contextvars import ContextVar

#: Request-scoped Garmin Personal API key. Set by GarminKeyMiddleware at the
#: start of each HTTP request and reset when the request finishes. Outside a
#: request (stdio mode, tests without the fixture) this is None.
current_garmin_key: ContextVar[str | None] = ContextVar(
    "fitness_mcp_current_garmin_key", default=None
)

#: Short stable identifier derived from the key. 16 hex chars of sha256 is
#: 64 bits of collision resistance — plenty for a POC with a small user base.
current_tenant_id: ContextVar[str | None] = ContextVar(
    "fitness_mcp_current_tenant_id", default=None
)


def tenant_id_from_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
