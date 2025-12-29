"""
E2E test: registration -> verify email -> enable 2FA -> login triggers 2FA requirement -> verify 2FA
"""
import pytest
import pyotp
from sqlalchemy import select


def test_registration_to_login_with_2fa_required(client, monkeypatch, db_session):
    # 1) Register user
    def fake_process_web_events_reg(events, username):
        return {
            'status': 'success',
            'features': {'username': username, 'data_type': 'enrollment'},
            'real_password_string': 'StrongPass123!',
            'password_hash': None
        }
    monkeypatch.setattr('app.blueprints.api.process_web_events', fake_process_web_events_reg)
    monkeypatch.setattr('app.blueprints.api.db_manager.save_data', lambda data: True, raising=False)
    import app.services.email_service as es
    monkeypatch.setattr(es.email_service, 'generate_token', lambda email, salt=None: 'flow-token', raising=False)
    monkeypatch.setattr(es.email_service, 'send_verification_email', lambda u, t: True, raising=False)

    resp = client.post('/api/register_sample', json={'username': 'flowuser', 'events': [{'type':'k','key':'a'}], 'email':'flow@example.com'})
    assert resp.status_code == 200

    from app.models import User, KeystrokeVector, db
    user = db.session.execute(select(User).where(User.username == 'flowuser')).scalars().first()
    assert user is not None

    # 2) Verify email
    import app.services.email_service as es
    monkeypatch.setattr(es.email_service, 'verify_token', lambda token, email, sent_at: (True, None), raising=False)
    resp = client.post('/api/verify_email', json={'username': 'flowuser', 'token': 'flow-token'})
    assert resp.status_code == 200

    user = db.session.execute(select(User).where(User.username == 'flowuser')).scalars().first()
    assert user.email_verified is True

    # 3) Enroll and confirm 2FA
    resp = client.post('/api/2fa/enroll', json={'username': 'flowuser'})
    assert resp.status_code == 200
    secret = resp.get_json().get('secret')
    assert secret

    totp = pyotp.TOTP(secret)
    token = totp.now()
    resp = client.post('/api/2fa/confirm', json={'username': 'flowuser', 'token': token})
    assert resp.status_code == 200

    user = db.session.execute(select(User).where(User.username == 'flowuser')).scalars().first()
    assert user.two_factor_enabled is True

    # 4) Seed additional enrollment samples to reach ready_for_login (10 samples total)
    # Create 10 enrollment samples (ready for login)
    for i in range(10):
        kv = KeystrokeVector(user_id=user.id, username=user.username, H_vector='[0.1, 0.2, 0.3]', DD_vector='[0.05,0.06,0.07]', UD_vector='[0.15,0.16,0.17]', data_type='enrollment')
        db_session.add(kv)
    db_session.commit()

    # 5) Attempt login; mock process_web_events for login and biometric verification to pass
    def fake_process_web_events_login(events, username):
        return {
            'status': 'success',
            'features': {'username': username, 'H_vector':[0.1,0.2,0.3], 'DD_vector':[0.05,0.06,0.07], 'UD_vector':[0.15,0.16,0.17], 'data_type':'verification', 'real_password_string':'StrongPass123!'},
            'real_password_string': 'StrongPass123!'
        }
    monkeypatch.setattr('app.blueprints.api.process_web_events', fake_process_web_events_login)

    # Mock BiometricService to return verified and require 2FA path
    from app.blueprints import api as api_mod
    monkeypatch.setattr(api_mod.biometric_service, 'verify_keystroke_sample', lambda *a, **k: {'success': True, 'verified': True, 'score': 0.9, 'confidence': 'High'}, raising=True)

    resp = client.post('/api/login', json={'username':'flowuser', 'events':[{'type':'k','key':'a'}]})
    j = resp.get_json()
    assert resp.status_code == 200
    assert j.get('requires_2fa') is True

    # 6) Verify 2FA token via /api/2fa/verify
    totp2 = pyotp.TOTP(secret)
    token2 = totp2.now()
    resp = client.post('/api/2fa/verify', json={'username':'flowuser', 'token': token2})
    assert resp.status_code == 200
    assert resp.get_json().get('success') is True
