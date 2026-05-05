"""
Service registry scaffold.

This module provides an additive registry abstraction that can be introduced
without changing existing singleton imports. Route wiring migration can happen
in a later slice.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class ServiceRegistry:
    """Register and resolve services by key, with optional lazy providers."""

    def __init__(self) -> None:
        self._instances: dict[str, Any] = {}
        self._providers: dict[str, Callable[[], Any]] = {}

    def register(
        self,
        name: str,
        service: Any = None,
        *,
        provider: Callable[[], Any] | None = None,
        replace: bool = False,
    ) -> None:
        """Register a concrete service instance or a lazy provider.

        Exactly one of ``service`` or ``provider`` must be supplied.
        """
        if not name:
            raise ValueError("Service name must be a non-empty string")

        has_service = service is not None
        has_provider = provider is not None
        if has_service == has_provider:
            raise ValueError("Provide exactly one of service or provider")

        if not replace and self.has(name):
            raise KeyError(f"Service '{name}' is already registered")

        # Keep only one registration source for a key.
        self._instances.pop(name, None)
        self._providers.pop(name, None)

        if provider is not None:
            self._providers[name] = provider
        else:
            self._instances[name] = service

    def has(self, name: str) -> bool:
        """Return True when a service key is registered."""
        return name in self._instances or name in self._providers

    def get(self, name: str) -> Any:
        """Resolve a service by key.

        Lazy providers are evaluated once and memoized as concrete instances.
        """
        if name in self._instances:
            return self._instances[name]

        if name in self._providers:
            provider = self._providers.pop(name)
            instance = provider()
            self._instances[name] = instance
            return instance

        raise KeyError(f"Service '{name}' is not registered")

    def list_registered(self) -> list[str]:
        """Return all registered keys in stable sorted order."""
        return sorted(self._instances.keys() | self._providers.keys())
