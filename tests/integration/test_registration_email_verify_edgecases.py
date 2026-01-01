from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import User, db


def test_verify_invalid_token(client, monkeypatch, db_session):
    username = "invalidtoken"
    email = "inv@example.com"

    # Prepare user via register sample (mock processing)
    def fake_process(events, username_arg):
        return {
            "status": "success",
            "features": {"H_vector": [0.1], "DD_vector": [0.1]},
            "real_password_string": "Pass123!",
        }

    monkeypatch.setattr("app.blueprints.api.process_web_events", fake_process)
    monkeypatch.setattr(
        "app.blueprints.api.assess_sample_quality",
        lambda f: {"quality_label": "good", "quality_score": 0.9},
    )

    # Create user by first sample
    resp = client.post(
        "/api/register_sample",
        json={
            "username": username,
            "events": [{"type": "k", "key": "a"}],
            "email": email,
        },
    )
    assert resp.status_code == 200

    # Monkeypatch token generation & sending
    import app.services.email_service as es

    monkeypatch.setattr(
        es.email_service,
        "generate_token",
        lambda e, salt=None: "right-token",
        raising=False,
    )
    monkeypatch.setattr(
        es.email_service, "send_verification_email", lambda u, t: True, raising=False
    )

    resp = client.post("/api/send_verification", json={"username": username, "email": email})
    assert resp.status_code == 200

    # Try verify with wrong token
    bad = client.post("/api/verify_email", json={"username": username, "token": "bad-token"})
    assert bad.status_code == 400
    assert bad.get_json().get("error_code") == "invalid_token"

    u = db.session.execute(select(User).where(User.username == username)).scalars().first()
    assert u.email_verified is not True


def test_verify_expired_token(client, monkeypatch, db_session):
    username = "expireduser"
    email = "exp@example.com"

    def fake_process(events, username_arg):
        return {
            "status": "success",
            "features": {"H_vector": [0.1], "DD_vector": [0.1]},
            "real_password_string": "Pass123!",
        }

    monkeypatch.setattr("app.blueprints.api.process_web_events", fake_process)
    monkeypatch.setattr(
        "app.blueprints.api.assess_sample_quality",
        lambda f: {"quality_label": "good", "quality_score": 0.9},
    )

    resp = client.post(
        "/api/register_sample",
        json={
            "username": username,
            "events": [{"type": "k", "key": "a"}],
            "email": email,
        },
    )
    assert resp.status_code == 200

    import app.services.email_service as es

    monkeypatch.setattr(
        es.email_service,
        "generate_token",
        lambda e, salt=None: "exp-token",
        raising=False,
    )
    monkeypatch.setattr(
        es.email_service, "send_verification_email", lambda u, t: True, raising=False
    )

    resp = client.post("/api/send_verification", json={"username": username, "email": email})
    assert resp.status_code == 200

    # Expire the token by setting timestamp back
    u = db.session.execute(select(User).where(User.username == username)).scalars().first()
    u.email_verification_sent_at = datetime.now(timezone.utc) - timedelta(hours=5)
    db.session.commit()

    resp = client.post("/api/verify_email", json={"username": username, "token": "exp-token"})
    assert resp.status_code == 400
    assert resp.get_json().get("error_code") == "expired_token"
    u = db.session.execute(select(User).where(User.username == username)).scalars().first()
    assert u.email_verified is not True


def test_resend_updates_token(client, monkeypatch, db_session):
    username = "resenduser"
    email = "resend@example.com"

    def fake_process(events, username_arg):
        return {
            "status": "success",
            "features": {"H_vector": [0.2], "DD_vector": [0.2]},
            "real_password_string": "Pass123!",
        }

    monkeypatch.setattr("app.blueprints.api.process_web_events", fake_process)
    monkeypatch.setattr(
        "app.blueprints.api.assess_sample_quality",
        lambda f: {"quality_label": "good", "quality_score": 0.9},
    )

    resp = client.post(
        "/api/register_sample",
        json={
            "username": username,
            "events": [{"type": "k", "key": "a"}],
            "email": email,
        },
    )
    assert resp.status_code == 200

    import app.services.email_service as es

    monkeypatch.setattr(
        es.email_service, "generate_token", lambda e, salt=None: "first", raising=False
    )
    monkeypatch.setattr(
        es.email_service, "send_verification_email", lambda u, t: True, raising=False
    )

    resp = client.post("/api/send_verification", json={"username": username, "email": email})
    assert resp.status_code == 200

    # Capture first sent timestamp
    u = db.session.execute(select(User).where(User.username == username)).scalars().first()
    first_sent = u.email_verification_sent_at

    # Resend with a different token (stateless token implementation)
    monkeypatch.setattr(
        es.email_service,
        "generate_token",
        lambda e, salt=None, sent_at=None: "second",
        raising=False,
    )
    r = client.post("/api/resend_verification", json={"username": username})
    assert r.status_code == 200

    u = db.session.execute(select(User).where(User.username == username)).scalars().first()
    assert u.email_verification_sent_at is not None
    assert u.email_verification_sent_at != first_sent

    # Mock verify_token to accept only the newest token
    monkeypatch.setattr(
        es.email_service,
        "verify_token",
        lambda token, email, sent_at: ((True, None) if token == "second" else (False, "invalid")),
        raising=False,
    )
    ok = client.post("/api/verify_email", json={"username": username, "token": "second"})
    assert ok.status_code == 200
    bad_old = client.post("/api/verify_email", json={"username": username, "token": "first"})
    assert bad_old.status_code == 400
