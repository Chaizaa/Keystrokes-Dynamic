"""Quick smoke checks for critical auth/dashboard API paths.

Run with:
    .\\venv\\Scripts\\python.exe quick_smoke.py
"""

from __future__ import annotations

import sys

from app import create_app
from app.models import User, db
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.compiler import compiles


@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(_type, _compiler, **_kw):
    return "CHAR(32)"


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_status(resp, expected: int, label: str) -> None:
    ensure(
        resp.status_code == expected,
        f"{label}: expected {expected}, got {resp.status_code}",
    )


def login_session(client, user_id: int) -> None:
    """Set authenticated session directly for smoke checks."""
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True
        sess["login_time"] = "smoke-test"


def build_events_from_password(password: str, start_ms: int = 1000, step_ms: int = 90):
    """Build synthetic keydown/keyup event stream accepted by process_web_events()."""
    events = []
    current = start_ms
    for char in password:
        if char.isalpha():
            code = f"Key{char.upper()}"
        elif char.isdigit():
            code = f"Digit{char}"
        else:
            # Fallback for punctuation in synthetic smoke data.
            code = f"Key{char.upper()}"

        events.append({"t": current, "evt": "d", "code": code, "key": char})
        events.append({"t": current + 45, "evt": "u", "code": code, "key": char})
        current += step_ms
    return events


def main() -> int:
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        user = User(username="smoke_user", email="smoke@example.com", email_verified=True)
        user.set_password("SmokePass123!")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    client = app.test_client()

    # Public route checks
    for path in (
        "/",
        "/login",
        "/register",
        "/dataset",
        "/verify?username=smoke_user",
        "/health/live",
        "/health/ready",
    ):
        resp = client.get(path, follow_redirects=False)
        assert_status(resp, 200, f"GET {path}")

    # The reset pages now require an active server-side reset session; without
    # one they redirect to login (no dead form, no identity in the URL).
    resp = client.get("/reset/verify-code", follow_redirects=False)
    assert_status(resp, 302, "GET /reset/verify-code (no reset session)")
    resp = client.get("/reset/complete", follow_redirects=False)
    assert_status(resp, 302, "GET /reset/complete (no reset session)")

    # Anonymous access to protected dashboard should redirect to login
    for path in ("/home", "/dashboard"):
        resp = client.get(path, follow_redirects=False)
        assert_status(resp, 302, f"GET {path} (anonymous)")

    # Register/reset related endpoint smoke
    resp = client.post("/api/check_username", json={"username": "smoke_new", "mode": "register"})
    assert_status(resp, 200, "POST /api/check_username")

    # Register/login smoke with synthetic keystroke events
    flow_password = "smokepass1"
    flow_events = build_events_from_password(flow_password)
    flow_username = "smoke_flow"

    register_resp = client.post(
        "/api/register_sample",
        json={
            "username": flow_username,
            "email": "smoke_flow@example.com",
            "events": flow_events,
        },
    )
    assert_status(register_resp, 200, "POST /api/register_sample")
    register_body = register_resp.get_json() or {}
    ensure(register_body.get("status") == "success", "Expected success status from /api/register_sample")

    login_resp = client.post(
        "/api/login",
        json={
            "username": flow_username,
            "events": flow_events,
        },
    )
    ensure(
        login_resp.status_code != 500,
        f"POST /api/login returned 500 (body={login_resp.get_data(as_text=True)})",
    )

    # send_reset_verification is intentionally anti-enumeration: it ALWAYS
    # returns a generic 200 success, never revealing whether the email/username
    # exists (and an empty body simply does nothing).
    resp = client.post("/api/send_reset_verification", json={})
    assert_status(resp, 200, "POST /api/send_reset_verification (generic)")
    ensure(
        (resp.get_json() or {}).get("success") is True,
        "send_reset_verification should return generic success",
    )

    resp = client.post("/api/verify_reset", json={})
    assert_status(resp, 400, "POST /api/verify_reset (missing payload)")

    resp = client.post("/api/reset_password", json={})
    assert_status(resp, 400, "POST /api/reset_password (missing payload)")

    # Authenticated checks
    login_session(client, user_id)

    for path in ("/home", "/dashboard"):
        resp = client.get(path, follow_redirects=False)
        assert_status(resp, 200, f"GET {path} (authenticated)")

    info_resp = client.get("/api/user/info", follow_redirects=False)
    assert_status(info_resp, 200, "GET /api/user/info")
    info_body = info_resp.get_json() or {}
    ensure(info_body.get("username") == "smoke_user", "Unexpected username in /api/user/info")
    ensure("has_password" in info_body, "Missing has_password in /api/user/info")
    ensure("api_key_count" in info_body, "Missing api_key_count in /api/user/info")

    # Authenticated reset endpoint should validate missing fields
    resp = client.post("/api/user/reset_password", json={})
    assert_status(resp, 400, "POST /api/user/reset_password (missing payload)")

    # Dashboard API key endpoints
    key_list_resp = client.get("/api/user/api-keys?include_inactive=true")
    assert_status(key_list_resp, 200, "GET /api/user/api-keys?include_inactive=true")
    list_body = key_list_resp.get_json() or {}
    ensure(list_body.get("success") is True, "Expected success=true for API key list")

    bad_gen_resp = client.post("/api/user/api-keys/generate", json={})
    assert_status(bad_gen_resp, 400, "POST /api/user/api-keys/generate (missing partner_name)")

    gen_payload = {
        "partner_name": "Smoke Partner",
        "description": "Quick smoke key",
        "rate_limit": 120,
        "allowed_origins": "example.com",
        "expires_days": 30,
    }
    gen_resp = client.post("/api/user/api-keys/generate", json=gen_payload)
    assert_status(gen_resp, 200, "POST /api/user/api-keys/generate")
    gen_body = gen_resp.get_json() or {}
    ensure(gen_body.get("success") is True, "Expected success=true when generating API key")
    ensure(bool(gen_body.get("api_key")), "Expected raw api_key in generate response")
    generated_key = (gen_body.get("key") or {})
    key_id = generated_key.get("id")
    ensure(isinstance(key_id, int), "Expected key.id in generate response")

    list_after_resp = client.get("/api/user/api-keys?include_inactive=true")
    assert_status(list_after_resp, 200, "GET /api/user/api-keys after generate")
    list_after_body = list_after_resp.get_json() or {}
    ensure(len(list_after_body.get("keys") or []) >= 1, "Expected at least one key after generate")

    deactivate_resp = client.post(f"/api/user/api-keys/{key_id}/deactivate", json={})
    assert_status(deactivate_resp, 200, "POST /api/user/api-keys/<id>/deactivate")

    active_only_resp = client.get("/api/user/api-keys")
    assert_status(active_only_resp, 200, "GET /api/user/api-keys (active only)")
    active_only_body = active_only_resp.get_json() or {}
    ensure(len(active_only_body.get("keys") or []) == 0, "Expected no active keys after deactivation")

    # Authenticated reset-password happy-path smoke.
    reset_resp = client.post(
        "/api/user/reset_password",
        json={
            "current_password": "SmokePass123!",
            "new_password": "NewSmoke456!",
        },
    )
    assert_status(reset_resp, 200, "POST /api/user/reset_password (happy path)")
    reset_body = reset_resp.get_json() or {}
    ensure(reset_body.get("success") is True, "Expected success=true for /api/user/reset_password")

    # Endpoint should now require login again because reset_password logs user out.
    post_reset_info = client.get("/api/user/info", follow_redirects=False)
    assert_status(post_reset_info, 302, "GET /api/user/info after reset logout")

    print("SMOKE_CHECK: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as err:
        print(f"SMOKE_CHECK: FAIL -> {err}")
        raise SystemExit(1)
    except Exception as err:  # pragma: no cover - smoke guard
        print(f"SMOKE_CHECK: ERROR -> {err}")
        raise SystemExit(1)
