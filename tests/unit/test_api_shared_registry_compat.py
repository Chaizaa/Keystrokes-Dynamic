import app.blueprints.api as api_mod
from app.blueprints.api import _shared as shared_mod
from app.blueprints.api import enrollment as enrollment_mod
from app.blueprints.api import login as login_mod
from app.services import ServiceRegistry


def test_shared_registry_contains_core_services():
    assert shared_mod.service_registry.has("auth_service") is True
    assert shared_mod.service_registry.has("biometric_service") is True


def test_shared_exports_are_service_proxies():
    assert repr(shared_mod.auth_service).startswith("<ServiceProxy")
    assert repr(shared_mod.biometric_service).startswith("<ServiceProxy")


def test_resolved_services_match_default_registry():
    assert shared_mod.get_service("auth_service") is shared_mod.service_registry.get("auth_service")
    assert shared_mod.get_service("biometric_service") is shared_mod.service_registry.get("biometric_service")
    assert shared_mod.get_auth_service() is shared_mod.service_registry.get("auth_service")
    assert shared_mod.get_biometric_service() is shared_mod.service_registry.get("biometric_service")


def test_api_package_reexports_shared_singletons():
    assert api_mod.auth_service is shared_mod.auth_service
    assert api_mod.biometric_service is shared_mod.biometric_service
    assert api_mod.get_service is shared_mod.get_service
    assert api_mod.get_auth_service is shared_mod.get_auth_service
    assert api_mod.get_biometric_service is shared_mod.get_biometric_service


def test_route_modules_keep_same_service_instances():
    assert login_mod.auth_service is shared_mod.auth_service
    assert login_mod.biometric_service is shared_mod.biometric_service
    assert enrollment_mod.auth_service is shared_mod.auth_service
    assert enrollment_mod.biometric_service is shared_mod.biometric_service


def test_app_extensions_registry_matches_shared_export(app):
    assert app.extensions.get("service_registry") is shared_mod.service_registry


def test_service_resolution_prefers_app_extensions_registry(app, monkeypatch):
    class _FakeAuthService:
        marker = "fake-auth"

    class _FakeBiometricService:
        marker = "fake-biometric"

    replacement_registry = ServiceRegistry()
    replacement_registry.register("auth_service", _FakeAuthService())
    replacement_registry.register("biometric_service", _FakeBiometricService())

    with app.app_context():
        monkeypatch.setitem(app.extensions, "service_registry", replacement_registry)
        assert shared_mod.get_service("auth_service").marker == "fake-auth"
        assert shared_mod.get_service("biometric_service").marker == "fake-biometric"
        assert shared_mod.get_auth_service().marker == "fake-auth"
        assert shared_mod.get_biometric_service().marker == "fake-biometric"
        assert shared_mod.auth_service.marker == "fake-auth"
        assert shared_mod.biometric_service.marker == "fake-biometric"
