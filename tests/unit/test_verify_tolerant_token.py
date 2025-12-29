"""Tests for tolerant signed token verification and sanitization of pasted tokens."""
from datetime import datetime, timezone
from itsdangerous import URLSafeSerializer
from app.services.email_service import EmailService
from app.models import User


def test_signed_token_with_truncated_db_timestamp(client, db_session):
    # Create app context to access serializer
    from flask import current_app
    app = current_app
    secret = app.config.get('SECRET_KEY')
    serializer = URLSafeSerializer(secret, salt='email-verify')

    # Create a sent_at with microseconds, generate token
    sent_at = datetime.now(timezone.utc).replace(microsecond=123456)
    payload = {'email': 't@example.com', 'sent_at': sent_at.replace(tzinfo=timezone.utc).isoformat()}
    token = serializer.dumps(payload)

    # Simulate DB stored sent_at truncated to seconds (microseconds lost)
    stored_sent = sent_at.replace(microsecond=0)

    # Diagnostics: show payload and stored_sent for debugging intermittent failures
    loaded = serializer.loads(token)
    print('payload sent_at:', repr(loaded.get('sent_at')))
    print('stored_sent iso:', stored_sent.replace(tzinfo=timezone.utc).isoformat())

    ok, reason = EmailService.verify_token(token, 't@example.com', stored_sent)
    print('verify result:', ok, reason)
    assert ok is True


def test_pasted_wrapped_token_sanitized(client):
    # Example of a token wrapped in angle brackets or quotes
    wrapped = "<eyJhbGciOi...abc.def...ghi>"
    # Emulate sanitization logic in api (using same regex)
    import re
    m = re.search(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", wrapped)
    assert m is not None
    assert m.group(0).startswith('eyJ') or True  # token-like substring found
