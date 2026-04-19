from app.services import ServiceRegistry


def test_verify_user_uses_app_extensions_registry(client, app, monkeypatch):
    import app.blueprints.api as api_mod

    class _FakeAuthService:
        def get_user_by_identifier(self, _identifier):
            return None

        def login_user_session(self, _user):
            return True

    class _FakeBiometricService:
        def get_enrollment_status(self, _username):
            return {"count": 7, "ready_for_login": False, "enrolled": False}

        def verify_keystroke_sample(self, _username, _features):
            return {
                "success": True,
                "verified": True,
                "score": 0.93,
                "confidence": "high",
                "templates_used": 5,
            }

    monkeypatch.setattr(
        api_mod,
        "process_web_events",
        lambda _events, _username: {
            "status": "success",
            "features": {"total_duration": 0.5, "typing_speed": 2.0},
        },
    )

    replacement_registry = ServiceRegistry()
    replacement_registry.register("auth_service", _FakeAuthService())
    replacement_registry.register("biometric_service", _FakeBiometricService())

    with app.app_context():
        monkeypatch.setitem(app.extensions, "service_registry", replacement_registry)
        resp = client.post(
            "/api/verify_user",
            json={"username": "registry_login_user", "events": [{"evt": "d"}]},
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "success"
    assert data["score"] == 0.93
