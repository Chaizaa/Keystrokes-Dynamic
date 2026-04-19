"""
Shared state for the api blueprint package.

All route modules import ``api_bp``, ``auth_service``, and ``biometric_service``
from here so there is exactly one instance of each.
"""

from __future__ import annotations

from flask import Blueprint

from app import limiter
from app.services import AuthService, BiometricService, ServiceRegistry
from app.services.resolution import resolve_service

api_bp = Blueprint("api", __name__)

# Service layer registry (additive scaffold)
service_registry = ServiceRegistry()
service_registry.register("auth_service", provider=AuthService)
service_registry.register("biometric_service", provider=BiometricService)


def _resolve_service(name: str):
	"""Resolve service from app-bound registry when available, else fallback."""
	return resolve_service(name, fallback_registry=service_registry)


class _ServiceProxy:
	"""Proxy that defers attribute access to the active service instance."""

	def __init__(self, name: str):
		object.__setattr__(self, "_name", name)

	def __getattr__(self, attr):
		return getattr(_resolve_service(self._name), attr)

	def __setattr__(self, attr, value):
		setattr(_resolve_service(self._name), attr, value)

	def __repr__(self) -> str:
		return f"<ServiceProxy {self._name}>"


def get_service(name: str):
	"""Return resolved service instance for explicit call sites/tests."""
	return _resolve_service(name)


def get_auth_service():
	"""Return auth service resolved from the active registry."""
	return get_service("auth_service")


def get_biometric_service():
	"""Return biometric service resolved from the active registry."""
	return get_service("biometric_service")


# Keep legacy exports unchanged for route modules and tests while allowing
# request-time resolution from app.extensions["service_registry"].
auth_service = _ServiceProxy("auth_service")
biometric_service = _ServiceProxy("biometric_service")
