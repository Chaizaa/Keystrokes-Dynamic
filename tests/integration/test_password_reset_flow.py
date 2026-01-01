import json

import pytest

from app.models import User
from app.models import db as sa_db


def test_password_reset_flow(client, monkeypatch, db_session):
    """Integration test: send reset verification, verify it, submit a reset sample, and ensure password updated.

    Steps:
    1. Create a test user (via fixtures or DB session)
    2. Monkeypatch email_service.send_verification_email to capture the short code
    3. POST /api/send_reset_verification for username
    4. Read captured code, POST /api/verify_reset with code
    5. Receive reset_token from verify_reset
    6. POST a minimal keystroke enrollment sample to /api/reset_password with reset_token
    7. Assert response success and that user's password_hash is set
    """
    # Create user via DB session helper (conftest provides db_session)
    username = "reset_test_user"
    email = "reset_test@example.com"
    # Ensure no existing user (ORM)
    sa_db.session.query(User).filter_by(username=username).delete()
    sa_db.session.commit()
    # Create a user row without password
    user = User(username=username, email=email, email_verified=False)
    sa_db.session.add(user)
    sa_db.session.commit()

    captured = {}

    def fake_send(user, token, purpose=None):
        # Capture token (short code or signed token)
        captured["code"] = token
        return True

    monkeypatch.setattr(
        "app.services.email_service.email_service.send_verification_email",
        fake_send,
        raising=False,
    )

    # Step 1: request reset verification
    resp = client.post("/api/send_reset_verification", json={"username": username})
    assert resp.status_code == 200
    j = resp.get_json()
    assert j.get("success") is True

    # The app stored a hashed short code in DB; fake_send captured the clear code
    code = captured.get("code")
    assert code is not None

    # Step 2: verify reset code
    resp = client.post("/api/verify_reset", json={"username": username, "token": code})
    assert resp.status_code == 200
    j = resp.get_json()
    assert j.get("success") is True
    reset_token = j.get("reset_token")
    assert reset_token

    # Step 3: submit a minimal keystroke sample for reset
    # Build JS-like events: for each character emit a 'd' (down) then 'u' (up)
    password = "Password1"  # length >=6 so strength >= 0.5
    events = []
    t = 0
    for ch in password:
        code = "Key" + ch.upper() if ch.isalpha() else ("Digit" + ch if ch.isdigit() else "Minus")
        events.append({"t": t, "evt": "d", "code": code, "key": ch})
        t += 120
        events.append({"t": t, "evt": "u", "code": code, "key": ch})
        t += 80

    resp = client.post(
        "/api/reset_password",
        json={"username": username, "reset_token": reset_token, "events": events},
    )
    assert resp.status_code == 200
    j = resp.get_json()
    assert j.get("status") == "success" or j.get("progress")

    # Confirm user's password_hash is set in DB
    u = sa_db.session.query(User).filter_by(username=username).first()
    assert u is not None
    assert getattr(u, "password_hash", None) is not None
