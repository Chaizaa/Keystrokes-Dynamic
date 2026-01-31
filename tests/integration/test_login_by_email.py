import pytest

from app.models import User, db


def test_login_with_email_identifier(client, db_session, monkeypatch):
    # Create user with email
    user = User(username="emailuser", email="emailuser@example.com")
    user.set_password("EmailPass123")
    # Mark email as verified for login
    user.email_verified = True
    db.session.add(user)
    db.session.commit()

    # Mock enrollment status and verification to succeed
    import app.blueprints.api as api_mod

    monkeypatch.setattr(
        api_mod.biometric_service,
        "get_enrollment_status",
        lambda u: {"count": 10, "enrolled": True, "ready_for_login": True},
    )
    monkeypatch.setattr(
        api_mod.biometric_service,
        "verify_keystroke_sample",
        lambda username, features: {
            "success": True,
            "verified": True,
            "score": 0.95,
            "confidence": "high",
            "templates_used": 1,
        },
    )

    # Minimal valid keystroke events (two keys 'a' and 'b')
    base = 200000.0
    events = [
        {"evt": "d", "key": "a", "code": "KeyA", "t": base + 0},
        {"evt": "u", "key": "a", "code": "KeyA", "t": base + 120},
        {"evt": "d", "key": "b", "code": "KeyB", "t": base + 300},
        {"evt": "u", "key": "b", "code": "KeyB", "t": base + 420},
    ]

    payload = {"username": "emailuser@example.com", "events": events}
    resp = client.post("/api/login", json=payload)
    assert resp.status_code == 200
    j = resp.get_json()
    assert j.get("success") is True
    assert "message" in j
