from app.services import ServiceRegistry


def test_user_info_uses_app_extensions_registry(authenticated_client, app, monkeypatch):
    class _FakeBiometricService:
        def get_enrollment_status(self, _username):
            return {"count": 42, "ready_for_login": True, "enrolled": True}

    class _FakeAuthService:
        def change_password(self, _username, _current_password, _new_password):
            return True, "ok"

    replacement_registry = ServiceRegistry()
    replacement_registry.register("auth_service", _FakeAuthService())
    replacement_registry.register("biometric_service", _FakeBiometricService())

    with app.app_context():
        monkeypatch.setitem(app.extensions, "service_registry", replacement_registry)
        resp = authenticated_client.get("/api/user/info")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["enrollment_count"] == 42
    assert data["enrollment_ready"] is True


def test_user_reset_password_uses_app_extensions_registry(authenticated_client, app, monkeypatch):
    calls = []

    class _FakeBiometricService:
        def get_enrollment_status(self, _username):
            return {"count": 0, "ready_for_login": False, "enrolled": False}

    class _FakeAuthService:
        def change_password(self, username, current_password, new_password):
            calls.append((username, current_password, new_password))
            return True, "ok"

    replacement_registry = ServiceRegistry()
    replacement_registry.register("auth_service", _FakeAuthService())
    replacement_registry.register("biometric_service", _FakeBiometricService())

    with app.app_context():
        monkeypatch.setitem(app.extensions, "service_registry", replacement_registry)
        resp = authenticated_client.post(
            "/api/user/reset_password",
            json={"current_password": "any-current", "new_password": "new-pass"},
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert calls
    assert calls[0][1] == "any-current"
    assert calls[0][2] == "new-pass"
