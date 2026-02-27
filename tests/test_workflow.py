"""
End-to-end workflow test: register (20 keystroke samples) → login success.

Happy path only:
1. check_username (register mode)  → status == "available"
2. 20 × register_sample            → each returns status == "success"
3. check_username (login mode)     → exists=True, can_login=True
4. login                           → success=True
"""

import json

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASSWORD = "testpassword"   # 12 chars → strength score = 1.0, all lowercase
USERNAME = "testworkflow01"


def make_events(password: str, base_t: int = 1000, hold_ms: int = 80, gap_ms: int = 70) -> list:
    """Build a minimal keydown+keyup event list for a pure-lowercase password."""
    events = []
    t = base_t
    for ch in password:
        if ch.isalpha():
            code = f"Key{ch.upper()}"
        elif ch.isdigit():
            code = f"Digit{ch}"
        else:
            code = ch  # fallback
        events.append({"evt": "d", "key": ch, "code": code, "t": t})
        events.append({"evt": "u", "key": ch, "code": code, "t": t + hold_ms})
        t += hold_ms + gap_ms
    return events


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

def test_register_and_login_workflow(client, db_session):
    """Full register-then-login happy path."""

    # ------------------------------------------------------------------
    # STEP 1: check_username in register mode → should be 'available'
    # ------------------------------------------------------------------
    resp = client.post(
        "/api/check_username",
        data=json.dumps({"username": USERNAME, "mode": "register"}),
        content_type="application/json",
    )
    assert resp.status_code == 200, f"check_username (register) → {resp.status_code}: {resp.data}"
    body = resp.get_json()
    assert body.get("status") == "available", f"Expected 'available', got: {body}"

    # ------------------------------------------------------------------
    # STEP 2: submit 20 enrollment samples
    # ------------------------------------------------------------------
    for i in range(20):
        # Add a tiny per-sample offset so timestamps look realistic
        events = make_events(PASSWORD, base_t=1000 + i * 5)
        resp = client.post(
            "/api/register_sample",
            data=json.dumps({"username": USERNAME, "events": events}),
            content_type="application/json",
        )
        body = resp.get_json()
        assert resp.status_code == 200, f"Sample {i + 1}/20 → {resp.status_code}: {body}"
        assert body.get("status") == "success", f"Sample {i + 1}/20 failed: {body}"

    # ------------------------------------------------------------------
    # STEP 3: check_username in login mode → can_login must be True
    # ------------------------------------------------------------------
    resp = client.post(
        "/api/check_username",
        data=json.dumps({"username": USERNAME, "mode": "login"}),
        content_type="application/json",
    )
    assert resp.status_code == 200, f"check_username (login) → {resp.status_code}: {resp.data}"
    body = resp.get_json()
    assert body.get("exists") is True, f"User should exist: {body}"
    assert body.get("can_login") is True, f"should be ready to login: {body}"

    # ------------------------------------------------------------------
    # STEP 4: login — biometric verification must pass
    # ------------------------------------------------------------------
    events = make_events(PASSWORD, base_t=1000)
    resp = client.post(
        "/api/login",
        data=json.dumps({"username": USERNAME, "events": events}),
        content_type="application/json",
    )
    body = resp.get_json()
    assert resp.status_code == 200, f"Login → {resp.status_code}: {body}"
    assert body.get("success") is True, f"Login not successful: {body}"
