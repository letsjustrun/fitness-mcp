"""Per-request Garmin provider resolution.

HTTP transport
--------------
The ASGI middleware sets `current_garmin_key` and `current_tenant_id` on the
context var. `get_garmin_provider()` returns a `GarminProvider` instance
dedicated to that tenant, with its own on-disk Garmin bearer-token cache so
users never share bearer tokens.

Instances are memoized per tenant in-process so repeated requests reuse the
same `requests.Session` and the same cached Garmin bearer. Memory grows with
distinct users — acceptable for a POC.

Stdio transport
---------------
No middleware runs; context vars are None. We fall back to the env-only
`GARMIN_PERSONAL_API_KEY` for a single-user local install.

Tests
-----
`set_test_provider(tenant_id, provider)` injects a fake. The lookup checks
the test map before ever touching network/auth code.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from ..auth import current_garmin_key, current_tenant_id, tenant_id_from_key
from ..config import get_settings
from ..errors import ProviderAuthError
from .base import Provider
from .garmin import GarminProvider

log = logging.getLogger(__name__)


_cache: dict[str, Provider] = {}
_cache_lock = asyncio.Lock()

#: Test hook. If a tenant_id maps here, we return the override instead of
#: building a real GarminProvider. Set via `set_test_provider`.
_test_overrides: dict[str, Provider] = {}

#: Where to keep each tenant's Garmin bearer-token JSON cache. On HF Spaces
#: this is wiped between container restarts, which is harmless — the key
#: itself keeps working, we just re-exchange once.
_TOKEN_CACHE_DIR = Path("/tmp/fitness_mcp/garmin-tokens")


async def get_garmin_provider() -> tuple[Provider, str]:
    """Resolve the Garmin provider for the current request.

    Returns a (provider, tenant_id) pair. The tenant_id is the hash of the
    user's Garmin key — safe to use in SQL, log lines, and cache paths.
    """
    key = current_garmin_key.get()
    if key is None:
        # stdio fallback
        s = get_settings()
        if not s.garmin_personal_api_key:
            raise ProviderAuthError(
                "No Garmin Personal API key available. HTTP clients must send "
                "'Authorization: Bearer <your-garmin-key>'. Stdio installs "
                "should set GARMIN_PERSONAL_API_KEY in their environment."
            )
        key = s.garmin_personal_api_key
    tenant = current_tenant_id.get() or tenant_id_from_key(key)

    # Tests first — never touch GarminProvider when a fake is wired in.
    if tenant in _test_overrides:
        return _test_overrides[tenant], tenant

    async with _cache_lock:
        provider = _cache.get(tenant)
        if provider is None:
            s = get_settings()
            _TOKEN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_file = _TOKEN_CACHE_DIR / f"{tenant}.json"
            provider = GarminProvider(
                api_key=key,
                http_timeout=s.http_timeout_seconds,
                ca_bundle=str(s.ca_bundle) if s.ca_bundle else None,
                token_cache_file=str(cache_file),
            )
            _cache[tenant] = provider
            log.info("Garmin provider created for tenant %s", tenant)
    return provider, tenant


def set_test_provider(tenant_id: str, provider: Provider) -> None:
    _test_overrides[tenant_id] = provider


def clear_test_providers() -> None:
    _test_overrides.clear()


async def close_all() -> None:
    """Graceful shutdown: close all cached providers."""
    async with _cache_lock:
        for p in list(_cache.values()):
            try:
                await p.close()
            except Exception as e:  # noqa: BLE001
                log.warning("error closing provider: %s", e)
        _cache.clear()
