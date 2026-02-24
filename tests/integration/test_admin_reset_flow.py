import pytest
from sqlalchemy import select


def test_admin_send_reset_triggers_email_and_token_valid(client, monkeypatch, db_session):
    """Integration test: admin can trigger reset email; email send called with signed token."""
    from app.models import User, db
    from app.services import email_service as es_mod

    # Create admin user
    admin = User(username="admintest")
    admin.set_password("AdminPass123!")
    admin.role = "admin"
    db.session.add(admin)
    db.session.commit()

    # Create target user
    target = User(username="targetuser", email="target@example.com")
    target.set_password("UserPass123!")
    db.session.add(target)
    db.session.commit()

    # Capture arguments passed to send_verification_email
    captured = {}

    def fake_send_verification_email(user, token, purpose=None):
        captured['user'] = user
        captured['token'] = token
        captured['purpose'] = purpose
        return True

    monkeypatch.setattr(es_mod.email_service, 'send_verification_email', fake_send_verification_email, raising=False)

    # Login as admin via admin login endpoint
    resp = client.post('/admin/login', json={'username': 'admintest', 'password': 'AdminPass123!'})
    assert resp.status_code == 200

    # Trigger admin send_reset
    resp2 = client.post(f'/admin/user/{target.id}/send_reset')
    j = resp2.get_json()
    assert resp2.status_code == 200
    assert j.get('success') is True

    # Ensure email send was called with purpose 'reset'
    assert captured.get('user') is not None
    assert captured.get('purpose') == 'reset'
    token = captured.get('token')
    assert token

    # Verify the signed token is valid using the service verify_signed_token
    ok, reason = es_mod.email_service.verify_signed_token(token, target.email, target.email_verification_sent_at, salt='password-reset')
    assert ok is True, f"Signed token invalid: {reason}"
