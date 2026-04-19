import pytest

from app.models import User, db


def test_login_skips_rate_limit_in_dev_and_allows_relaxed_score(
    client, db_session, monkeypatch, app
):
    # Set dev lenient in app config
    app.config["DEV_LENIENT_RATELIMIT"] = True

    # Create user and set password
    user = User(username="devuser")
    user.set_password("DevPass123")
    db.session.add(user)
    db.session.commit()

    # Make recent failed >= 5 to simulate lockout
    import app.blueprints.api as api_mod

    monkeypatch.setattr(
        "app.models.LoginAttempt.get_recent_failed_attempts",
        lambda u, minutes=15: 6,
    )

    # Ensure enrollment present
    monkeypatch.setattr(
        api_mod.biometric_service,
        "get_enrollment_status",
        lambda u: {"count": 12, "enrolled": True, "ready_for_login": True},
    )

    # Make verification return slightly below threshold
    fake_verif = {
        "success": True,
        "verified": False,
        "score": 0.695,
        "confidence_score": 0.695,
        "avg_score": 0.69,
        "confidence": "low",
        "templates_used": 5,
    }
    monkeypatch.setattr(
        api_mod.biometric_service,
        "verify_keystroke_sample",
        lambda username, features: fake_verif,
    )

    base = 200000.0
    events = [
        {"evt": "d", "key": "a", "code": "KeyA", "t": base + 0},
        {"evt": "u", "key": "a", "code": "KeyA", "t": base + 120},
        {"evt": "d", "key": "b", "code": "KeyB", "t": base + 300},
        {"evt": "u", "key": "b", "code": "KeyB", "t": base + 420},
    ]

    payload = {"username": "devuser", "events": events, "debug": True}
    resp = client.post("/api/login", json=payload)
    assert resp.status_code == 200
    j = resp.get_json()
    assert j.get("success") is True
    # In dev relaxation, verification_result should include relaxed flag when applicable
    # We can check logs but here we assert success
