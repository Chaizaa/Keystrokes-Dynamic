import pytest
from sqlalchemy import select

from app.models import User, db


def test_register_sample_persists_for_existing_user(client, db_session, monkeypatch):
    """Existing user with 0 samples should be able to save a first sample and it should persist."""
    # Create an existing user with no enrollment samples
    user = User(username="persistuser")
    user.set_password("TestPass123!")
    db.session.add(user)
    db.session.commit()

    # Ensure legacy biometric DB has no pre-existing samples for this username
    import sqlite3

    from app.blueprints.api import db_manager

    conn = sqlite3.connect(db_manager.db_path)
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM user_vectors WHERE username = ?", ("persistuser",))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()

    assert db_manager.get_enrollment_count("persistuser") == 0

    # Mock processing to return a valid features object and password string
    def fake_process(events, username):
        return {
            "status": "success",
            "features": {"H_vector": [0.1, 0.2], "DD_vector": [0.05, 0.06]},
            "real_password_string": "TestPass123!",
            "password_hash": None,
        }

    monkeypatch.setattr("app.blueprints.api.process_web_events", fake_process)
    monkeypatch.setattr(
        "app.blueprints.api.assess_sample_quality",
        lambda f: {"quality_label": "good", "quality_score": 0.9},
    )

    payload = {"username": "persistuser", "events": [{"type": "keydown", "key": "a"}]}

    resp = client.post("/api/register_sample", json=payload)
    assert resp.status_code == 200, resp.get_json()
    j = resp.get_json()
    assert j.get("status") == "success"

    # Now the legacy DB should report 1 sample for this user
    assert db_manager.get_enrollment_count("persistuser") == 1
