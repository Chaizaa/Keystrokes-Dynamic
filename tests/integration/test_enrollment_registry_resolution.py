from app.services import ServiceRegistry


def test_check_username_uses_app_extensions_registry(client, app, monkeypatch):
    class _FakeAuthService:
        def get_user_by_email(self, _identifier):
            return None

        def check_username_availability(self, _username):
            return {
                "available": False,
                "exists": False,
                "reason": "resumable",
                "message": "Resume enrollment",
                "enrollment_count": 99,
            }

    class _FakeBiometricService:
        RECOMMENDED_SAMPLES = 10

        def get_recommended_samples(self):
            return 10

        def get_enrollment_status(self, _username):
            return {"count": 7, "enrolled": False, "ready_for_login": False}

    replacement_registry = ServiceRegistry()
    replacement_registry.register("auth_service", _FakeAuthService())
    replacement_registry.register("biometric_service", _FakeBiometricService())

    with app.app_context():
        monkeypatch.setitem(app.extensions, "service_registry", replacement_registry)
        resp = client.post(
            "/api/check_username",
            json={"username": "resume_user", "mode": "register"},
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "resumable"
    assert data["message"] == "Resume enrollment"
    assert data["enrollment_count"] == 7
