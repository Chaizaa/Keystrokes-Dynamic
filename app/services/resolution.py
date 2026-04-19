"""Service resolution helpers for registry-aware dependency access."""

from __future__ import annotations

from typing import Any

from flask import current_app, has_app_context


def resolve_service(name: str, *, fallback_registry: Any | None = None) -> Any:
    """Resolve a service from app registry, optionally falling back to another registry."""
    if has_app_context():
        registry = current_app.extensions.get("service_registry")
        if registry is not None:
            return registry.get(name)

    if fallback_registry is not None:
        return fallback_registry.get(name)

    raise RuntimeError(
        f"{name} is not available in app service registry and no fallback registry was provided"
    )


def resolve_service_from_app(name: str) -> Any:
    """Resolve a service strictly from app.extensions['service_registry']."""
    if not has_app_context():
        raise RuntimeError("Service resolution requires an active Flask application context")

    registry = current_app.extensions.get("service_registry")
    if registry is None or not registry.has(name):
        raise RuntimeError(f"{name} is not available in app service registry")

    return registry.get(name)
