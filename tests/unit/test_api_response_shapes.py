"""
Tests to ensure API response shapes remain compatible with frontend normalization logic.
"""

import pytest
from sqlalchemy import select


def test_check_username_response_shape(client, db_session):
    """Check /api/check_username returns fields the frontend expects"""
    resp = client.post("/api/check_username", json={"username": "some_random_user_123"})
    assert resp.status_code in (200, 400)
    data = resp.get_json()
    # Must include either 'status' or 'available'
    assert ("status" in data) or ("available" in data)
    # Must include enrollment_count (or equivalent)
    assert "enrollment_count" in data or "count" in data
    # message is helpful
    assert "message" in data or "msg" in data


def test_register_sample_returns_expected_shape(client, monkeypatch, db_session):
    """Ensure /api/register_sample returns 'status' or success-like responses and progress when successful"""

    # Mock processing to always succeed and not require a real password
    def fake_process(events, username):
        return {
            "status": "success",
            "features": {"username": username},
            "real_password_string": "TestPass123!",
            "password_hash": None,
        }

    monkeypatch.setattr("app.blueprints.api.process_web_events", fake_process)
    # Avoid legacy DB writes
    monkeypatch.setattr("app.blueprints.api.db_manager.save_data", lambda data: True, raising=False)

    payload = {
        "username": "testshapeuser",
        "events": [{"type": "keydown", "key": "a"}],
        "email": "testshape@example.com",
    }

    resp = client.post("/api/register_sample", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    # Accept either modern shape with 'status' or 'progress'
    assert "status" in data or "progress" in data
    # If success, progress.current should be present
    if data.get("status") == "success" or data.get("progress"):
        progress = data.get("progress") or {}
        # Validate progress fields
        assert "current" in progress and "target" in progress
