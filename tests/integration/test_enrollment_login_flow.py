import pytest
from sqlalchemy import select
from app.models import User, db

from app.blueprints.api import db_manager, biometric_service


def test_enrollment_and_login_verification(client, db_session, monkeypatch):
    """Enroll 20 samples for a user, then attempt login verification.
    Ensures BiometricService sees the enrolled templates (db count >= 20) during verification.
    """
    username = 'test_integration_user'
    test_password = 'TestPass123!'

    # Clean up any existing user rows and legacy DB samples for a clean start
    try:
        db.session.execute(select(User).where(User.username == username)).scalars().all()
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

    # Mock processing to always return a valid features object and the same password
    def fake_process(events, username_arg):
        return {
            'status': 'success',
            'features': {
                'H_vector': [0.1, 0.2],
                'DD_vector': [0.05, 0.06]
            },
            'real_password_string': test_password,
            'password_hash': None
        }

    monkeypatch.setattr('app.blueprints.api.process_web_events', fake_process)
    monkeypatch.setattr('app.blueprints.api.assess_sample_quality', lambda f: {'quality_label': 'good', 'quality_score': 0.95})

    payload = {
        'username': username,
        'events': [{'type': 'keydown', 'key': 'a'}],
        'email': 'ti@example.com'
    }

    # Enroll 20 samples
    for i in range(20):
        resp = client.post('/api/register_sample', json=payload)
        assert resp.status_code == 200, resp.get_json()
        j = resp.get_json()
        assert j.get('status') == 'success'

    # Now the DB should report >=20 samples for this user
    count = db_manager.get_enrollment_count(username)
    assert count >= 20

    # Mark the user's email as verified (not under test here; ensure login isn't blocked by unverified email)
    u = db.session.execute(select(User).where(User.username == username)).scalars().first()
    u.email_verified = True
    db.session.commit()

    # Spy on BiometricService.verify_keystroke_sample to assert it sees >=20 samples
    def spy_verify(username_arg, features_arg, *args, **kwargs):
        # Support both call styles: (username, features) or (features, templates)
        # Determine the username to check
        resolved_username = None
        if isinstance(username_arg, str):
            resolved_username = username_arg
        elif isinstance(username_arg, dict):
            # If features were passed first, try to extract username from templates (features_arg)
            # features_arg may be templates list in this call pattern
            templates = features_arg if isinstance(features_arg, list) else []
            if templates and isinstance(templates[0], dict) and templates[0].get('username'):
                resolved_username = templates[0].get('username')
            else:
                # Fallback to the test's username variable
                resolved_username = username
        else:
            resolved_username = username

        # Ensure DB reports the expected count
        current = db_manager.get_enrollment_count(resolved_username)
        assert current >= 20, f"Expected >=20 samples before verification but got {current}"
        return {
            'success': True,
            'verified': True,
            'score': 0.95,
            'confidence': 'high'
        }

    monkeypatch.setattr('app.blueprints.api.biometric_service.verify_keystroke_sample', spy_verify)

    # For login, process_web_events will return the same password and features
    login_resp = client.post('/api/login', json={'username': username, 'events': [{'type': 'keydown', 'key': 'a'}]})
    assert login_resp.status_code == 200, login_resp.get_json()
    j = login_resp.get_json()
    assert j.get('success') is True
    assert j.get('score', 0) >= 0.9
