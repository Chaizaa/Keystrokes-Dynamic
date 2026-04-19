"""
Ensure /api/register_sample treats weak passwords as advisory-only on first enrollment.
"""

import pytest


def test_register_sample_allows_weak_password_as_advisory(client, monkeypatch, db_session):
    # Simulate process_web_events returning a short/weak password for first sample
    def fake_process(events, username):
        return {
            "status": "success",
            "features": {"username": username},
            "real_password_string": "abc",
            "password_hash": None,
        }

    monkeypatch.setattr("app.blueprints.api.process_web_events", fake_process)

    payload = {
        "username": "weakpassuser",
        "events": [{"type": "keydown", "key": "a"}],
        "email": None,
    }

    resp = client.post("/api/register_sample", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("status") == "success"
    assert "progress" in data
