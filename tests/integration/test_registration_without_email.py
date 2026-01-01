import pytest
from sqlalchemy import select

from app.blueprints.api import db_manager
from app.models import User, db


def test_enroll_without_email_allows_creation_and_login(client, db_session, monkeypatch):
    username = "noemail_user"
    test_password = "NoEmailPass123!"

    # Cleanup any existing records
    try:
        db.session.query(User).filter(User.username == username).delete()
        db.session.commit()
    except Exception:
        db.session.rollback()

    # Ensure legacy DB has no pre-existing samples for this username
    import sqlite3

    conn = sqlite3.connect(db_manager.db_path)
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM user_vectors WHERE username = ?", (username,))
        cur.execute("DELETE FROM feature_vectors WHERE username = ?", (username,))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()

    assert db_manager.get_enrollment_count(username) == 0

    # Mock processing and quality
    def fake_process(events, username_arg):
        return {
            "status": "success",
            "features": {"H_vector": [0.1, 0.2], "DD_vector": [0.05, 0.06]},
            "real_password_string": test_password,
            "password_hash": None,
        }

    monkeypatch.setattr("app.blueprints.api.process_web_events", fake_process)
    monkeypatch.setattr(
        "app.blueprints.api.assess_sample_quality",
        lambda f: {"quality_label": "good", "quality_score": 0.95},
    )

    payload = {
        "username": username,
        "events": [{"type": "keydown", "key": "a"}],
        "email": None,
    }

    # Enroll 20 samples
    for i in range(20):
        resp = client.post("/api/register_sample", json=payload)
        assert resp.status_code == 200, resp.get_json()
        j = resp.get_json()
        assert j.get("status") == "success"

    # Now the DB should report >=20 samples for this user
    count = db_manager.get_enrollment_count(username)
    assert count >= 20

    # Confirm user exists and has no email
    u = db.session.execute(select(User).where(User.username == username)).scalars().first()
    assert u is not None
    assert u.email in (None, "")

    # Spy on biometric verify to assert >=20 samples before login
    def spy_verify(username_arg, features_arg, *args, **kwargs):
        current = db_manager.get_enrollment_count(username)
        assert current >= 20
        return {"success": True, "verified": True, "score": 0.95, "confidence": "high"}

    monkeypatch.setattr("app.blueprints.api.biometric_service.verify_keystroke_sample", spy_verify)

    # Attempt login using keystrokes
    login_resp = client.post(
        "/api/login",
        json={"username": username, "events": [{"type": "keydown", "key": "a"}]},
    )
    assert login_resp.status_code == 200, login_resp.get_json()
    j = login_resp.get_json()
    assert j.get("success") is True
    assert j.get("score", 0) >= 0.9
