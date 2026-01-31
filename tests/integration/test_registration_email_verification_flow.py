import pytest
from sqlalchemy import select

from app.models import User, db


def test_registration_completes_and_email_verifies(client, monkeypatch, db_session):
    """Register a user (20 samples), request verification, then verify token."""
    username = "emailflow"
    email = "emailflow@example.com"

    # Mock process to return a valid sample and password
    def fake_process(events, username_arg):
        return {
            "status": "success",
            "features": {"H_vector": [0.1, 0.2], "DD_vector": [0.05, 0.06]},
            "real_password_string": "StrongPass123!",
        }

    monkeypatch.setattr("app.blueprints.api.process_web_events", fake_process)
    monkeypatch.setattr(
        "app.blueprints.api.assess_sample_quality",
        lambda f: {"quality_label": "good", "quality_score": 0.9},
    )

    # Clean previous user
    db.session.query(User).filter(User.username == username).delete()
    db.session.commit()

    # First sample: creates user (email required)
    resp = client.post(
        "/api/register_sample",
        json={
            "username": username,
            "events": [{"type": "k", "key": "a"}],
            "email": email,
        },
    )
    assert resp.status_code == 200, resp.get_json()

    # Add remaining 19 samples
    for i in range(19):
        resp = client.post(
            "/api/register_sample",
            json={
                "username": username,
                "events": [{"type": "k", "key": "a"}],
                "email": email,
            },
        )
        assert resp.status_code == 200

    # Monkeypatch email service functions used by /send_verification
    import app.services.email_service as es

    monkeypatch.setattr(
        es.email_service,
        "generate_token",
        lambda email, salt=None: "test-token",
        raising=False,
    )
    monkeypatch.setattr(
        es.email_service, "send_verification_email", lambda u, t: True, raising=False
    )

    # Now request verification email explicitly
    resp = client.post("/api/send_verification", json={"username": username, "email": email})
    assert resp.status_code == 200

    # Check DB for sent timestamp (we use stateless tokens)
    user = db.session.execute(select(User).where(User.username == username)).scalars().first()
    assert user is not None
    assert user.email_verification_sent_at is not None

    # The test monkeypatches generate_token to return a simple string; make verify_token accept it
    import app.services.email_service as es

    monkeypatch.setattr(
        es.email_service,
        "verify_token",
        lambda token, email, sent_at: (True, None),
        raising=False,
    )

    # Use verify_email endpoint with the (mocked) token
    resp = client.post("/api/verify_email", json={"username": username, "token": "test-token"})
    assert resp.status_code == 200

    user = db.session.execute(select(User).where(User.username == username)).scalars().first()
    assert user.email_verified is True
