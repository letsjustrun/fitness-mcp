"""Provider registry.

Factories are lazy — missing credentials for one provider don't stop another
from working. The registry is a singleton (`default_registry`) but tests can
instantiate their own and inject fakes.
"""
from __future__ import annotations

import logging
from collections.abc import Callable

from ..config import get_settings
from ..errors import ProviderAuthError
from .base import Provider
from .garmin import GarminProvider

log = logging.getLogger(__name__)


class ProviderRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, Callable[[], Provider]] = {}
        self._instances: dict[str, Provider] = {}

    def register(self, name: str, factory: Callable[[], Provider]) -> None:
        self._factories[name] = factory

    def override(self, name: str, provider: Provider) -> None:
        """Test hook: inject a concrete provider and skip the factory."""
        self._instances[name] = provider

    def get(self, name: str) -> Provider:
        if name in self._instances:
            return self._instances[name]
        if name not in self._factories:
            raise KeyError(
                f"No provider '{name}'. Registered: {sorted(self._factories)}"
            )
        self._instances[name] = self._factories[name]()
        return self._instances[name]

    def names(self) -> list[str]:
        return sorted(self._factories)

    async def close_all(self) -> None:
        for p in list(self._instances.values()):
            try:
                await p.close()
            except Exception as e:  # noqa: BLE001
                log.warning("error closing provider %s: %s", p.name, e)
        self._instances.clear()


def _garmin_factory() -> Provider:
    s = get_settings()
    if not s.garmin_personal_api_key:
        raise ProviderAuthError(
            "GARMIN_PERSONAL_API_KEY is not set. See README for setup."
        )
    return GarminProvider(
        api_key=s.garmin_personal_api_key,
        http_timeout=s.http_timeout_seconds,
        ca_bundle=str(s.ca_bundle) if s.ca_bundle else None,
    )


default_registry = ProviderRegistry()
default_registry.register("garmin", _garmin_factory)
