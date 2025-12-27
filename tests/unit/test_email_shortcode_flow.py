"""Tests for short numeric verification code flow."""
from datetime import datetime, timezone, timedelta
from werkzeug.security import generate_password_hash
from sqlalchemy import select


def test_send_verification_sets_short_code(client, monkeypatch, db_session):
    # Prepare a user
    from app.models import User, db
    u = User(username='scuser', password_hash='hash')
    db.session.add(u)
    db.session.commit()

    captured = {}
    def fake_send(user, token):
        captured['token'] = token
        return True
    import app.services.email_service as es
    monkeypatch.setattr(es.email_service, 'send_verification_email', fake_send, raising=False)

    resp = client.post('/api/send_verification', json={'username': 'scuser', 'email': 'sc@example.com'})
    assert resp.status_code == 200, resp.get_json()

    user = db.session.execute(select(User).where(User.username == 'scuser')).scalars().first()
    assert user.email_verification_sent_at is not None
    assert user.email_verification_code_hash is not None
    # token sent should be 6 digit
    assert 'token' in captured
    assert isinstance(captured['token'], str)
    assert captured['token'].isdigit() and len(captured['token']) == 6


def test_verify_with_short_code_success(client, db_session):
    from app.models import User, db
    # create user and set code hash
    code = '123456'
    u = User(username='vuser', password_hash='h')
    u.email = 'v@example.com'
    u.email_verification_sent_at = datetime.now(timezone.utc)
    u.email_verification_code_hash = generate_password_hash(code)
    db.session.add(u)
    db.session.commit()

    resp = client.post('/api/verify_email', json={'username': 'vuser', 'token': code})
    assert resp.status_code == 200
    j = resp.get_json()
    assert j['success'] is True
    # user should be marked verified and hash cleared
    user = db.session.execute(select(User).where(User.username == 'vuser')).scalars().first()
    assert user.email_verified is True
    assert user.email_verification_code_hash is None


def test_verify_with_short_code_expired(client, db_session):
    from app.models import User, db
    code = '999999'
    u = User(username='euser', password_hash='h')
    u.email = 'e@example.com'
    # set sent at far in the past
    u.email_verification_sent_at = datetime.now(timezone.utc) - timedelta(hours=5)
    from werkzeug.security import generate_password_hash
    u.email_verification_code_hash = generate_password_hash(code)
    db.session.add(u)
    db.session.commit()

    resp = client.post('/api/verify_email', json={'username': 'euser', 'token': code})
    assert resp.status_code == 400
    j = resp.get_json()
    assert j['error_code'] == 'expired_token'