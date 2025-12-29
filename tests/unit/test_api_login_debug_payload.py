import pytest
from app.models import User, db


def test_login_returns_debug_payload_on_failure_when_debug_requested(client, db_session, monkeypatch):
    # Setup: create user and ensure sufficient enrollment via monkeypatch
    user = User(username='debuguser')
    user.set_password('DebugPass123')
    db.session.add(user)
    db.session.commit()

    # Ensure get_enrollment_status reports enough samples
    import app.blueprints.api as api_mod
    monkeypatch.setattr(api_mod.biometric_service, 'get_enrollment_status', lambda u: {'count': 10, 'enrolled': True, 'ready_for_login': True})

    # Mock verify to return failing but with debug info
    fake_verif = {'success': True, 'verified': False, 'score': 0.35, 'avg_score': 0.36, 'confidence': 'low', 'templates_used': 5}
    monkeypatch.setattr(api_mod.biometric_service, 'verify_keystroke_sample', lambda username, features: fake_verif)

    # Call the login endpoint with debug requested
    # Create minimal valid keystroke events (two keys 'a' and 'b')
    base = 100000.0
    events = [
        {'evt': 'd', 'key': 'a', 'code': 'KeyA', 't': base + 0},
        {'evt': 'u', 'key': 'a', 'code': 'KeyA', 't': base + 120},
        {'evt': 'd', 'key': 'b', 'code': 'KeyB', 't': base + 300},
        {'evt': 'u', 'key': 'b', 'code': 'KeyB', 't': base + 420},
    ]

    payload = {'username': 'debuguser', 'events': events, 'debug': True}
    resp = client.post('/api/login', json=payload)
    assert resp.status_code == 400
    j = resp.get_json()
    assert j.get('success') is False
    # Debug field should be present and match our fake_verif
    assert 'debug' in j
    assert j['debug']['score'] == pytest.approx(0.35)