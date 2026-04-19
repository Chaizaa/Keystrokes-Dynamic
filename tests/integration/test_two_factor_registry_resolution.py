from app.services import ServiceRegistry


def test_2fa_verify_uses_app_extensions_registry(client, app, monkeypatch):
    calls = []

    class _FakeAuthService:
        def verify_two_factor_token(self, username, token):
            calls.append((username, token))
            return True

    replacement_registry = ServiceRegistry()
    replacement_registry.register("auth_service", _FakeAuthService())

    with app.app_context():
        monkeypatch.setitem(app.extensions, "service_registry", replacement_registry)
        resp = client.post(
            "/api/2fa/verify",
            json={"username": "registry_2fa_user", "token": "123456"},
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert calls == [("registry_2fa_user", "123456")]


def test_2fa_verify_honors_registry_failure(client, app, monkeypatch):
    class _FakeAuthService:
        def verify_two_factor_token(self, _username, _token):
            return False

    replacement_registry = ServiceRegistry()
    replacement_registry.register("auth_service", _FakeAuthService())

    with app.app_context():
        monkeypatch.setitem(app.extensions, "service_registry", replacement_registry)
        resp = client.post(
            "/api/2fa/verify",
            json={"username": "registry_2fa_user", "token": "bad-token"},
        )

    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
