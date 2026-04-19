import pytest

from app.services import ServiceRegistry
from app.services.resolution import resolve_service, resolve_service_from_app


def test_resolve_service_uses_fallback_when_app_registry_missing(app, monkeypatch):
    fallback_registry = ServiceRegistry()
    expected_service = object()
    fallback_registry.register("auth_service", expected_service)

    with app.app_context():
        monkeypatch.delitem(app.extensions, "service_registry", raising=False)
        assert resolve_service("auth_service", fallback_registry=fallback_registry) is expected_service


def test_resolve_service_prefers_app_registry_over_fallback(app, monkeypatch):
    app_registry = ServiceRegistry()
    fallback_registry = ServiceRegistry()

    expected_service = object()
    fallback_service = object()

    app_registry.register("auth_service", expected_service)
    fallback_registry.register("auth_service", fallback_service)

    with app.app_context():
        monkeypatch.setitem(app.extensions, "service_registry", app_registry)
        assert resolve_service("auth_service", fallback_registry=fallback_registry) is expected_service


def test_resolve_service_from_app_requires_registry(app, monkeypatch):
    with app.app_context():
        monkeypatch.delitem(app.extensions, "service_registry", raising=False)
        with pytest.raises(RuntimeError, match="auth_service"):
            resolve_service_from_app("auth_service")
