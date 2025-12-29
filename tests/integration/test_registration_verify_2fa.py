"""
Integration tests for registration -> email verification -> 2FA enrollment flow
"""
import pytest
import pyotp
from datetime import datetime
from sqlalchemy import select


def test_registration_verify_email_and_enable_2fa(client, monkeypatch, db_session):
    # Step 1: Register user (mock process_web_events and prevent legacy DB writes)
    def fake_process_web_events(events, username):
        return {
            'status': 'success',
            'features': {'username': username, 'data_type': 'enrollment'},
            'real_password_string': 'StrongPass123!',
            'password_hash': None
        }
    monkeypatch.setattr('app.blueprints.api.process_web_events', fake_process_web_events)
    monkeypatch.setattr('app.blueprints.api.db_manager.save_data', lambda data: True, raising=False)

    import app.services.email_service as es
    monkeypatch.setattr(es.email_service, 'generate_token', lambda email, salt=None: 'reg-token', raising=False)
    monkeypatch.setattr(es.email_service, 'send_verification_email', lambda u, t: True, raising=False)

    payload = {
        'username': 'intuser',
        'events': [{'type': 'keydown', 'key': 'x'}],
        'email': 'int@example.com'
    }

    resp = client.post('/api/register_sample', json=payload)
    assert resp.status_code == 200

    # Verify user record and token
    from app.models import User, db
    user = db.session.execute(select(User).where(User.username == 'intuser')).scalars().first()
    assert user is not None
    assert user.email_verification_sent_at is not None

    # Step 2: Verify email via API (mock verify_token to accept reg-token)
    import app.services.email_service as es
    monkeypatch.setattr(es.email_service, 'verify_token', lambda token, email, sent_at: (True, None), raising=False)

    resp = client.post('/api/verify_email', json={'username': 'intuser', 'token': 'reg-token'})
    assert resp.status_code == 200
    j = resp.get_json()
    assert j['success'] is True

    user = db.session.execute(select(User).where(User.username == 'intuser')).scalars().first()
    assert user.email_verified is True

    # Step 3: Enroll 2FA
    resp = client.post('/api/2fa/enroll', json={'username': 'intuser'})
    assert resp.status_code == 200
    secret = resp.get_json().get('secret')
    assert secret is not None

    # Step 4: Confirm 2FA using generated TOTP
    totp = pyotp.TOTP(secret)
    token = totp.now()

    resp = client.post('/api/2fa/confirm', json={'username': 'intuser', 'token': token})
    assert resp.status_code == 200

    user = db.session.execute(select(User).where(User.username == 'intuser')).scalars().first()
    assert user.two_factor_enabled is True

    # Step 5: Verify 2FA token via API
    token = totp.now()
    resp = client.post('/api/2fa/verify', json={'username': 'intuser', 'token': token})
    assert resp.status_code == 200
    assert resp.get_json().get('success') is True
