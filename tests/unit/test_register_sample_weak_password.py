"""
Ensure /api/register_sample rejects too-weak passwords on first enrollment
"""

import pytest


def test_register_sample_rejects_weak_password(client, monkeypatch, db_session):
    # Simulate process_web_events returning a short/weak password for first sample
    def fake_process(events, username):
        return {
            "status": "success",
            "features": {"username": username},
            "real_password_string": "abc",
            "password_hash": None,
        }

    monkeypatch.setattr("app.blueprints.api.process_web_events", fake_process)
    # Avoid actual DB writes in this unit test (we expect rejection before save)
    monkeypatch.setattr("app.blueprints.api.db_manager.save_data", lambda data: None, raising=False)

    payload = {
        "username": "weakpassuser",
        "events": [{"type": "keydown", "key": "a"}],
        "email": None,
    }

    resp = client.post("/api/register_sample", json=payload)
    assert resp.status_code == 400
    data = resp.get_json()
    assert data.get("error_code") == "WEAK_PASSWORD"
    assert "Password terlalu lemah" in data.get("message", "")
