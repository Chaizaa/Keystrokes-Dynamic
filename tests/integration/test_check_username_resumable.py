"""Test /api/check_username returns resumable status and enrollment count when partial samples exist"""

import pytest


def test_check_username_resumable(client, monkeypatch):
    # Simulate AuthService returning reason 'resumable'
    from app.blueprints.api import auth_service, biometric_service

    def fake_availability(username):
        return {
            "available": False,
            "exists": False,
            "reason": "resumable",
            "message": "Resume enrollment",
            "enrollment_count": 3,
        }

    monkeypatch.setattr(auth_service, "check_username_availability", fake_availability)
    monkeypatch.setattr(
        biometric_service,
        "get_enrollment_status",
        lambda u: {"count": 3, "ready_for_login": False, "enrolled": False},
    )

    resp = client.post("/api/check_username", json={"username": "resume_user", "mode": "register"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "resumable"
    assert data["enrollment_count"] == 3
    assert data["is_retry"] is True
