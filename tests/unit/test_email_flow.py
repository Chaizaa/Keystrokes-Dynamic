"""
Tests for email verification behavior in registration flow.
"""

from datetime import datetime

import pytest
from sqlalchemy import select


def test_register_sample_email_send_failure_does_not_fail(client, monkeypatch, db_session):
    """If sending verification email fails, registration should still succeed and token should be recorded."""

    # Monkeypatch process_web_events to avoid real keystroke parsing
    def fake_process_web_events(events, username):
        return {
            "status": "success",
            "features": {"username": username, "data_type": "enrollment"},
            "real_password_string": "TestPass123!",
            "password_hash": None,
        }

    monkeypatch.setattr("app.blueprints.api.process_web_events", fake_process_web_events)

    # Monkeypatch EmailService methods on the shared email_service object (allow creating attributes)
    import app.services.email_service as es

    monkeypatch.setattr(
        es.email_service,
        "generate_token",
        lambda email, salt=None: "test-token",
        raising=False,
    )

    def raise_send(user, token):
        raise Exception("SMTP auth failed")

    monkeypatch.setattr(es.email_service, "send_verification_email", raise_send, raising=False)

    # Avoid writing to legacy SQLite during unit tests (legacy db_manager.save_data)
    monkeypatch.setattr("app.blueprints.api.db_manager.save_data", lambda data: True, raising=False)

    payload = {
        "username": "newuser",
        "events": [{"type": "keydown", "key": "a"}],
        "email": "user@example.com",
    }

    resp = client.post("/api/register_sample", json=payload)
    assert resp.status_code == 200, resp.get_json()
    j = resp.get_json()
    assert j["status"] == "success"

    # Ensure user exists and email sent timestamp was recorded despite send failure
    from app.models import User, db

    user = db.session.execute(select(User).where(User.username == "newuser")).scalars().first()
    assert user is not None
    assert user.email_verification_sent_at is not None


def test_register_sample_email_send_success_records_timestamp_and_token(
    client, monkeypatch, db_session
):
    """When verification email is sent successfully, token and timestamp are recorded."""

    def fake_process_web_events(events, username):
        return {
            "status": "success",
            "features": {"username": username, "data_type": "enrollment"},
            "real_password_string": "TestPass123!",
            "password_hash": None,
        }

    monkeypatch.setattr("app.blueprints.api.process_web_events", fake_process_web_events)

    import app.services.email_service as es

    monkeypatch.setattr(
        es.email_service,
        "generate_token",
        lambda email, salt=None: "ok-token",
        raising=False,
    )

    # Simulate a successful send (no exception)
    monkeypatch.setattr(
        es.email_service,
        "send_verification_email",
        lambda user, token: True,
        raising=False,
    )

    # Avoid writing to legacy SQLite during unit tests (legacy db_manager.save_data)
    monkeypatch.setattr("app.blueprints.api.db_manager.save_data", lambda data: True, raising=False)

    payload = {
        "username": "anothernew",
        "events": [{"type": "keydown", "key": "b"}],
        "email": "ok@example.com",
    }

    resp = client.post("/api/register_sample", json=payload)
    assert resp.status_code == 200, resp.get_json()
    j = resp.get_json()
    assert j["status"] == "success"

    from app.models import User, db

    user = db.session.execute(select(User).where(User.username == "anothernew")).scalars().first()
    assert user is not None
    assert user.email_verification_sent_at is not None
    assert isinstance(user.email_verification_sent_at, datetime)
