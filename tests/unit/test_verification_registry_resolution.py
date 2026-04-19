import app.blueprints.api.verification as verification_mod
from app.services import ServiceRegistry


def test_clear_enrollment_if_needed_uses_app_extensions_registry(app, monkeypatch):
    calls = []

    class _FakeBiometricService:
        def get_enrollment_status(self, username):
            calls.append(username)
            return {"count": 1, "ready_for_login": False, "enrolled": False}

    replacement_registry = ServiceRegistry()
    replacement_registry.register("auth_service", object())
    replacement_registry.register("biometric_service", _FakeBiometricService())

    with app.app_context():
        monkeypatch.setitem(app.extensions, "service_registry", replacement_registry)
        verification_mod._clear_enrollment_if_needed("registry_verification_user")

    assert calls == ["registry_verification_user"]
