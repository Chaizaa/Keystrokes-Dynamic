"""
Ensure /api/register_sample accepts null email without raising.
"""

import pytest


def test_register_with_null_email(client, monkeypatch, db_session):
    # Mock processing success and avoid legacy db writes
    def fake_process(events, username):
        return {
            "status": "success",
            "features": {"username": username},
            "real_password_string": "TestPass123!",
            "password_hash": None,
        }

    monkeypatch.setattr("app.blueprints.api.process_web_events", fake_process)
    monkeypatch.setattr("app.blueprints.api.db_manager.save_data", lambda data: None, raising=False)

    payload = {
        "username": "nulltest",
        "events": [{"type": "keydown", "key": "a"}],
        "email": None,
    }

    resp = client.post("/api/register_sample", json=payload)
    # Email is optional — expect successful save
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("status") == "success" or data.get("success") is True
