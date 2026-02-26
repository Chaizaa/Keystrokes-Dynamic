"""
End-to-End user flow test
==========================

Tests the complete lifecycle of a regular user account:

    Step 1  — check_username (register mode)       → available
    Step 2  — register_sample × 20                 → enrollment complete
    Step 3  — check_username (login mode)           → can_login = True
    Step 4  — login                                 → success = True
    Step 5  — GET /api/user/info                    → user data returned
    Step 6  — GET /auth/logout                      → redirects (session cleared)
    Step 7  — GET /api/user/info after logout       → 401 / redirect (not logged in)
    Step 8  — re-login                              → success = True
    Step 9  — POST /api/user/reset_password         → success = True
    Step 10 — re-login with OLD password            → rejected
    Step 11 — re-enroll with NEW password × 20      → enrollment complete
    Step 12 — login with NEW password               → success = True
    Step 13 — logout                                → session cleared

Run with:
    pytest tests/test_e2e_user_flow.py -v -s

Or standalone:
    python tests/test_e2e_user_flow.py
"""

import json
import sys
import os

import pytest
from sqlalchemy.pool import StaticPool

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
USERNAME     = "e2e_testuser_01"
PASSWORD     = "TestPass123!"   # strong: upper + lower + digit + special → score 1.0
NEW_PASSWORD = "NewPass456@"    # also strong

HOLD_MS  = 80    # key hold duration
GAP_MS   = 70    # between characters
SAMPLES  = 20    # enrollment target


# ---------------------------------------------------------------------------
# Keystroke event generator
# ---------------------------------------------------------------------------

def make_events(password: str, base_t: int = 1000, hold_ms: int = HOLD_MS,
                gap_ms: int = GAP_MS) -> list:
    """Build realistic keydown + keyup events for *password*.

    The ``key`` field carries the actual character (preserves case and special
    chars) so ``process_web_events`` reconstructs ``real_password_string``
    verbatim.  The ``code`` field is the physical key name; sequential
    non-overlapping timing means duplicate codes never collide in temp_dict.
    """
    _special_codes = {
        "!": "Digit1", "@": "Digit2", "#": "Digit3", "$": "Digit4",
        "%": "Digit5", "^": "Digit6", "&": "Digit7", "*": "Digit8",
        "(": "Digit9", ")": "Digit0", "-": "Minus",  "_": "Minus",
        "=": "Equal",  "+": "Equal",  "[": "BracketLeft", "]": "BracketRight",
        ";": "Semicolon", ":": "Semicolon", "'": "Quote", '"': "Quote",
        ",": "Comma",  ".": "Period", "/": "Slash",   "?": "Slash",
        "\\": "Backslash", "`": "Backquote", "~": "Backquote",
    }
    events = []
    t = base_t
    for ch in password:
        if ch.isalpha():
            code = f"Key{ch.upper()}"
        elif ch.isdigit():
            code = f"Digit{ch}"
        else:
            code = _special_codes.get(ch, f"Key_{ord(ch)}")
        events.append({"evt": "d", "key": ch, "code": code, "t": t})
        events.append({"evt": "u", "key": ch, "code": code, "t": t + hold_ms})
        t += hold_ms + gap_ms
    return events


# ---------------------------------------------------------------------------
# Pytest fixture: isolated Flask app + test client
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def e2e_app():
    """Flask app wired to an in-memory SQLite DB with DEV_LENIENT enabled."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app import create_app
    from app.models import db

    cfg = {
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SQLALCHEMY_ENGINE_OPTIONS": {
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        },
        "SECRET_KEY": "e2e-test-secret-key",
        "RATELIMIT_ENABLED": False,
        "DEV_LENIENT_RATELIMIT": True,   # relax biometric threshold by 0.05
        "SERVER_NAME": "localhost",
    }

    app = create_app(cfg)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture(scope="module")
def e2e_client(e2e_app):
    """Persistent test client (cookies kept across requests)."""
    with e2e_app.test_client() as client:
        yield client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _post_json(client, url: str, payload: dict):
    return client.post(url, data=json.dumps(payload), content_type="application/json")


def _get(client, url: str):
    return client.get(url, follow_redirects=False)


def _section(title: str):
    bar = "-" * 60
    print(f"\n{bar}")
    print(f"  {title}")
    print(bar)


def _ok(msg: str):
    print(f"  [OK]  {msg}")


def _info(msg: str):
    print(f"  [INFO] {msg}")


# ---------------------------------------------------------------------------
# The actual test — single function so session/cookies persist end-to-end
# ---------------------------------------------------------------------------

class TestE2EUserFlow:
    """Complete registration → login → logout → reset flow for a regular user."""

    # ------------------------------------------------------------------ step 1
    def test_01_check_username_register_mode(self, e2e_client):
        _section("STEP 1 — check_username (register mode)")
        resp = _post_json(e2e_client, "/api/check_username",
                          {"username": USERNAME, "mode": "register"})

        assert resp.status_code == 200, \
            f"Expected 200, got {resp.status_code}: {resp.data}"
        body = resp.get_json()
        _info(f"Response: {body}")
        assert body.get("status") == "available", \
            f"Username should be available for registration: {body}"
        assert body.get("exists") is False
        _ok(f"Username '{USERNAME}' is available")

    # ------------------------------------------------------------------ step 2
    def test_02_register_20_samples(self, e2e_client):
        _section("STEP 2 — register_sample × 20 (enrollment)")
        for i in range(SAMPLES):
            # Vary base_t slightly so each sample has distinct timing.
            # Note: no email provided → user created without email → login skips
            #       the email-verification gate (user.email is falsy).
            events = make_events(PASSWORD, base_t=1000 + i * 3)
            resp = _post_json(e2e_client, "/api/register_sample",
                              {"username": USERNAME, "events": events})
            body = resp.get_json()
            assert resp.status_code == 200, \
                f"Sample {i + 1}/{SAMPLES} → {resp.status_code}: {body}"
            assert body.get("status") == "success", \
                f"Sample {i + 1}/{SAMPLES} failed: {body}"
            progress = body.get("progress", {})
            _ok(f"Sample {i + 1:02d}/{SAMPLES}"
                f"  [progress: {progress.get('current')}/{progress.get('target')}]")

    # ------------------------------------------------------------------ step 3
    def test_03_check_username_login_mode(self, e2e_client):
        _section("STEP 3 — check_username (login mode) — verify enrollment")
        resp = _post_json(e2e_client, "/api/check_username",
                          {"username": USERNAME, "mode": "login"})

        assert resp.status_code == 200, \
            f"Expected 200, got {resp.status_code}: {resp.data}"
        body = resp.get_json()
        _info(f"Response: {body}")
        assert body.get("exists") is True, f"User should exist: {body}"
        assert body.get("can_login") is True, \
            f"User should be ready to login: {body}"
        assert body.get("enrollment_count") == SAMPLES, \
            f"Expected {SAMPLES} samples, got: {body.get('enrollment_count')}"
        _ok(f"User exists, enrollment_count={body['enrollment_count']}, can_login=True")

    # ------------------------------------------------------------------ step 4
    def test_04_login(self, e2e_client):
        _section("STEP 4 — login with biometric credentials")
        events = make_events(PASSWORD, base_t=1000)
        resp = _post_json(e2e_client, "/api/login",
                          {"username": USERNAME, "events": events})
        body = resp.get_json()
        _info(f"Response: {body}")
        assert resp.status_code == 200, \
            f"Login → {resp.status_code}: {body}"
        assert body.get("success") is True, \
            f"Login should succeed but got: {body}"
        _ok(f"Login successful  [score={body.get('score', 'n/a')!r}, "
            f"confidence={body.get('confidence_label', 'n/a')!r}]")

    # ------------------------------------------------------------------ step 5
    def test_05_get_user_info_authenticated(self, e2e_client):
        _section("STEP 5 — GET /api/user/info (must be authenticated)")
        resp = _get(e2e_client, "/api/user/info")
        body = resp.get_json()
        _info(f"Response: {body}")
        assert resp.status_code == 200, \
            f"Expected 200 while logged in, got {resp.status_code}: {resp.data}"
        assert body.get("username") == USERNAME
        assert body.get("enrollment_count") == SAMPLES
        assert body.get("enrollment_ready") is True
        _ok(f"User info returned: username={body['username']!r}, "
            f"enrollment_ready={body['enrollment_ready']}")

    # ------------------------------------------------------------------ step 6
    def test_06_logout(self, e2e_client):
        _section("STEP 6 \u2014 GET /logout")
        resp = _get(e2e_client, "/logout")
        # Logout redirects to landing — 302 or 200 after follow
        assert resp.status_code in (200, 302), \
            f"Expected redirect after logout, got {resp.status_code}"
        _ok("Logout successful (session cleared)")

    # ------------------------------------------------------------------ step 7
    def test_07_user_info_after_logout(self, e2e_client):
        _section("STEP 7 — GET /api/user/info after logout (must be rejected)")
        resp = _get(e2e_client, "/api/user/info")
        # Flask-Login returns 401 or redirects to login (302) for @login_required
        assert resp.status_code in (401, 302), \
            f"Expected 401/302 when not logged-in, got {resp.status_code}"
        _ok(f"Unauthenticated request correctly rejected (HTTP {resp.status_code})")

    # ------------------------------------------------------------------ step 8
    def test_08_relogin_before_password_reset(self, e2e_client):
        _section("STEP 8 — re-login before password reset")
        events = make_events(PASSWORD, base_t=1000)
        resp = _post_json(e2e_client, "/api/login",
                          {"username": USERNAME, "events": events})
        body = resp.get_json()
        _info(f"Response: {body}")
        assert resp.status_code == 200, \
            f"Re-login → {resp.status_code}: {body}"
        assert body.get("success") is True, \
            f"Re-login should succeed: {body}"
        _ok("Re-login successful")

    # ------------------------------------------------------------------ step 9
    def test_09_reset_password(self, e2e_client):
        _section("STEP 9 — POST /api/user/reset_password")
        resp = _post_json(e2e_client, "/api/user/reset_password", {
            "current_password": PASSWORD,
            "new_password": NEW_PASSWORD,
        })
        body = resp.get_json()
        _info(f"Response: {body}")
        assert resp.status_code == 200, \
            f"reset_password → {resp.status_code}: {body}"
        assert body.get("success") is True, \
            f"Password reset should succeed: {body}"
        _ok("Password reset successful — enrollment data cleared, session ended")

    # ---------------------------------------------------------------- step 10
    def test_10_login_with_old_password_fails(self, e2e_client):
        _section("STEP 10 — login with OLD password (must fail)")
        events = make_events(PASSWORD, base_t=1000)
        resp = _post_json(e2e_client, "/api/login",
                          {"username": USERNAME, "events": events})
        body = resp.get_json()
        _info(f"Response: {body}")
        # After reset, enrollment is wiped → should fail with no_enrollment or password mismatch
        assert resp.status_code in (400, 403, 404), \
            f"Login with old password should be rejected, got {resp.status_code}: {body}"
        assert body.get("success") is not True, \
            f"Login with old password must not succeed: {body}"
        _ok(f"Old password rejected as expected  [reason={body.get('reason', 'n/a')!r}]")

    # ---------------------------------------------------------------- step 11
    def test_11_re_enroll_with_new_password(self, e2e_client):
        _section("STEP 11 — re-enroll with NEW password × 20")
        for i in range(SAMPLES):
            events = make_events(NEW_PASSWORD, base_t=2000 + i * 3)
            resp = _post_json(e2e_client, "/api/register_sample",
                              {"username": USERNAME, "events": events})
            body = resp.get_json()
            assert resp.status_code == 200, \
                f"Re-enroll sample {i + 1}/{SAMPLES} → {resp.status_code}: {body}"
            assert body.get("status") == "success", \
                f"Re-enroll sample {i + 1}/{SAMPLES} failed: {body}"
            progress = body.get("progress", {})
            _ok(f"Sample {i + 1:02d}/{SAMPLES}"
                f"  [progress: {progress.get('current')}/{progress.get('target')}]")

    # ---------------------------------------------------------------- step 12
    def test_12_login_with_new_password(self, e2e_client):
        _section("STEP 12 — login with NEW password (must succeed)")
        events = make_events(NEW_PASSWORD, base_t=2000)
        resp = _post_json(e2e_client, "/api/login",
                          {"username": USERNAME, "events": events})
        body = resp.get_json()
        _info(f"Response: {body}")
        assert resp.status_code == 200, \
            f"Login with new password → {resp.status_code}: {body}"
        assert body.get("success") is True, \
            f"Login with new password should succeed: {body}"
        _ok(f"Login with new password successful  "
            f"[score={body.get('score', 'n/a')!r}]")

    # ---------------------------------------------------------------- step 13
    def test_13_final_logout(self, e2e_client):
        _section("STEP 13 — final logout")
        resp = _get(e2e_client, "/logout")
        assert resp.status_code in (200, 302), \
            f"Expected redirect after logout, got {resp.status_code}"
        _ok("Final logout successful -- full user lifecycle complete")

        _section("SUMMARY")
        _ok("REGISTRATION -> LOGIN -> USER INFO -> LOGOUT -> RESET PASSWORD -> RE-ENROLL -> LOGIN -> LOGOUT")
        _ok("All 13 steps passed.")


# ---------------------------------------------------------------------------
# Standalone runner (python tests/test_e2e_user_flow.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import pytest as _pytest
    sys.exit(_pytest.main([__file__, "-v", "-s", "--tb=short"]))
