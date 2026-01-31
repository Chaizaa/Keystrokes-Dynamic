import pytest
from sqlalchemy import select

from app.models import User, db


def test_register_sample_existing_user_can_set_password_on_first_sample(
    client, db_session, monkeypatch
):
    """If an existing user exists without a password, the first sample should set the password and persist."""
    # Create an existing user without setting a password
    user = User(username="nopassworduser")
    db.session.add(user)
    db.session.commit()

    # Ensure legacy biometric DB has no pre-existing samples for this username
    import sqlite3

    from app.blueprints.api import db_manager

    conn = sqlite3.connect(db_manager.db_path)
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM user_vectors WHERE username = ?", ("nopassworduser",))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()

    assert db_manager.get_enrollment_count("nopassworduser") == 0

    # Mock processing to return a valid features object and password string
    def fake_process(events, username):
        return {
            "status": "success",
            "features": {"H_vector": [0.1, 0.2], "DD_vector": [0.05, 0.06]},
            "real_password_string": "NewPassword!23",
            "password_hash": None,
        }

    monkeypatch.setattr("app.blueprints.api.process_web_events", fake_process)
    monkeypatch.setattr(
        "app.blueprints.api.assess_sample_quality",
        lambda f: {"quality_label": "good", "quality_score": 0.9},
    )

    payload = {
        "username": "nopassworduser",
        "events": [{"type": "keydown", "key": "a"}],
    }

    resp = client.post("/api/register_sample", json=payload)
    assert resp.status_code == 200, resp.get_json()
    j = resp.get_json()
    assert j.get("status") == "success"

    # Server should indicate we set the password on an existing account
    assert j.get("password_event") == "PASSWORD_SET_ON_EXISTING"

    # Now the legacy DB should report 1 sample for this user
    assert db_manager.get_enrollment_count("nopassworduser") == 1

    # And the user record should now have a password hash
    from app.services.auth_service import AuthService

    auth = AuthService()
    u = auth.get_user_by_username("nopassworduser")
    assert u is not None
    assert u.password_hash is not None or u.plain_password is not None
