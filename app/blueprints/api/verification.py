"""
Email verification, password-reset verification, and resend endpoints.
"""

from __future__ import annotations

import traceback
import uuid
from datetime import datetime, timezone
from typing import Optional


from flask import current_app, jsonify, request, session
from sqlalchemy import select

from app.models import AdminAudit, User, db
from app.services.email_service import email_service
from app.services.verification_service import verification_service
from app.utils.password_strength import calculate_password_strength
from app.utils.validators import is_valid_email

from app import limiter as _limiter
from ._shared import api_bp, get_biometric_service
from .helpers import error_response, save_biometric_sample


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_user(username: str) -> Optional[User]:
    if not username:
        return None
    return db.session.execute(select(User).where(User.username == username)).scalars().first()


def _fetch_user_by_email(email: str) -> Optional[User]:
    if not email:
        return None
    return db.session.execute(
        select(User).where(User.email == email.strip().lower())
    ).scalars().first()


# Session keys binding an in-flight reset to a specific account *server-side*.
# Identity for verify_reset / reset_password is read from here, never from the
# client request body — so the code/token can only ever be checked against the
# account that actually requested the reset, and the username/email never has to
# travel in a URL or be guessable by the caller.
_RESET_UID_KEY = "pwreset_uid"
_RESET_TOKEN_KEY = "pwreset_token"


def _resolve_reset_user() -> Optional[User]:
    """Return the account bound to the current reset session, or None."""
    uid = session.get(_RESET_UID_KEY)
    if not uid:
        return None
    try:
        return db.session.get(User, uuid.UUID(str(uid)))
    except (ValueError, TypeError):
        return None


def _clear_reset_session():
    session.pop(_RESET_UID_KEY, None)
    session.pop(_RESET_TOKEN_KEY, None)


# Server-side cooldown between consecutive code issues to the same user.
# This is independent of Flask-Limiter (which is per-IP) — an attacker rotating
# IPs or behind a NAT pool can bypass per-IP limits, but not this per-user one.
_CODE_REISSUE_COOLDOWN_SECONDS = 60


def _seconds_until_reissue_allowed(user, purpose: str) -> int:
    """Return remaining cooldown seconds before a new code may be issued.

    Returns 0 when no cooldown is active. The result is clamped to
    [0, _CODE_REISSUE_COOLDOWN_SECONDS] so that a stale or future
    timestamp (e.g. due to historical psycopg2 timezone-stripping into a
    naive column on a non-UTC PostgreSQL session) can never produce a
    multi-hour wait — the user is at worst delayed by the configured
    cooldown.
    """
    last_sent = (
        user.password_reset_sent_at if purpose == "user_reset"
        else user.email_verification_sent_at
    )
    if last_sent is None:
        return 0
    last_sent_utc = (
        last_sent.replace(tzinfo=timezone.utc)
        if last_sent.tzinfo is None else last_sent
    )
    elapsed = (datetime.now(timezone.utc) - last_sent_utc).total_seconds()
    remaining = _CODE_REISSUE_COOLDOWN_SECONDS - int(elapsed)
    if remaining <= 0:
        return 0
    return min(_CODE_REISSUE_COOLDOWN_SECONDS, remaining)


def _cooldown_response(retry_after: int):
    """Standardized 429 response when a per-user cooldown is active."""
    resp = jsonify({
        "success": False,
        "status": "error",
        "message": f"Tunggu {retry_after} detik sebelum meminta kode baru",
        "reason": "cooldown_active",
        "retry_after": retry_after,
    })
    resp.headers["Retry-After"] = str(retry_after)
    return resp, 429


def _utc_naive_now():
    """Return naive UTC datetime.

    The user/sent_at columns are declared as ``db.DateTime`` (no tz).
    Passing an aware datetime in causes psycopg2 to convert into the
    session timezone and then strip the tz info — on a non-UTC session
    this leaves a wall-clock value that the read path (which assumes
    naive == UTC) interprets as a future timestamp, producing absurd
    cooldown waits. Write naive UTC explicitly to avoid this.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _issue_and_send_code(user, purpose: str = None):
    """Generate, persist, and send a verification code."""
    code = verification_service.generate_6_digit_code()
    sent_at = _utc_naive_now()

    if purpose == "user_reset":
        user.password_reset_code_hash = verification_service.hash_code(code)
        user.password_reset_sent_at = sent_at
    else:
        user.email_verification_code_hash = verification_service.hash_code(code)
        user.email_verification_sent_at = sent_at

    db.session.commit()
    return email_service.send_verification_email(user, code, purpose=purpose)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@api_bp.route("/verify_email", methods=["POST"])
@_limiter.limit("10 per minute")
def verify_email():
    """Verify a user's email using the 6-digit code."""
    data = request.json or {}
    username = data.get("username")
    token = str(data.get("token", "")).strip()

    if not username or not token:
        return error_response("Data tidak lengkap", reason="invalid_input")

    user = _fetch_user(username)
    if not user:
        return error_response("User tidak ditemukan", reason="user_not_found", status_code=404)

    ok, reason = verification_service.verify_token(
        token, user.email, user.email_verification_sent_at, 
        code_hash=user.email_verification_code_hash
    )

    if not ok:
        return error_response(
            "Token tidak valid" if reason == "invalid" else "Token kadaluarsa",
            reason=f"{reason}_token"
        )

    user.email_verification_code_hash = None
    user.email_verified = True
    db.session.commit()
    return jsonify({"success": True, "message": "Email verified"}), 200


@api_bp.route("/send_verification", methods=["POST"])
@_limiter.limit("3 per minute;20 per hour")
def send_verification():
    """Send a verification code for a registration email.

    Only allowed when:
      - the username is not already a fully-registered account, AND
      - the email is not already bound to a different fully-registered account.
    A "pending" passwordless row may exist (re-issued code is OK), but we never
    create a new pending row owned by someone who can't yet prove ownership of
    the email — that prevented account-squat in the previous implementation.
    """
    data = request.json or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()

    if not username or not email:
        return error_response("Data tidak lengkap")

    if not is_valid_email(email):
        return error_response("Format email tidak valid", reason="invalid_email")

    user = _fetch_user(username)
    if user and getattr(user, "password_hash", None):
        return error_response(
            "Username sudah terdaftar",
            reason="username_taken",
            status_code=409,
        )

    email_owner = db.session.execute(
        select(User).where(User.email == email)
    ).scalars().first()
    if (
        email_owner
        and getattr(email_owner, "password_hash", None)
        and email_owner.username != username
    ):
        return error_response(
            "Email sudah digunakan akun lain",
            reason="email_taken",
            status_code=409,
        )

    created_new = False
    if not user:
        user = User(username=username, email=email, email_verified=False)
        db.session.add(user)
        db.session.commit()
        created_new = True
    elif user.email != email:
        # Pending row exists but with a different email — rebind email since
        # ownership of the username has not been proved yet (no password set).
        user.email = email
        user.email_verified = False
        db.session.commit()

    retry_after = _seconds_until_reissue_allowed(user, purpose="email_verify")
    if retry_after > 0:
        return _cooldown_response(retry_after)

    if _issue_and_send_code(user):
        return jsonify({"success": True, "message": "Email verifikasi terkirim", "created": created_new}), 200
    return error_response("Gagal mengirim email", status_code=500)


@api_bp.route("/send_reset_verification", methods=["POST"])
@_limiter.limit("3 per minute;20 per hour")
def send_reset_verification():
    """Initiate a password reset.

    Accepts ``{email}`` (public forgot-password on the login page) or
    ``{username}`` (authenticated dashboard reset). The response is ALWAYS the
    same generic success message: the endpoint never reveals whether an account
    exists, closing the user/email-enumeration vector. When a real, fully
    registered account is matched we bind the reset to it server-side via the
    session (``pwreset_uid``); the identity is never echoed back to the client.

    Per-user cooldown via ``password_reset_sent_at`` still throttles real sends
    even if the per-IP Flask-Limiter is bypassed (rotated IPs / disabled limiter).
    """
    data = request.json or {}
    email = (data.get("email") or "").strip().lower()
    username = (data.get("username") or "").strip()

    generic_ok = jsonify({
        "success": True,
        "message": "Jika akun terkait terdaftar, kode reset telah dikirim ke email-nya.",
    })

    user = None
    if email:
        user = _fetch_user_by_email(email) if is_valid_email(email) else None
    elif username:
        user = _fetch_user(username)
    else:
        # No identity in the body (e.g. "Resend" on the verify-code page during
        # the public flow) — fall back to the session-bound account.
        user = _resolve_reset_user()

    # Only act for a real, fully-registered account that has an email on file.
    if user and user.email and getattr(user, "password_hash", None):
        retry_after = _seconds_until_reissue_allowed(user, purpose="user_reset")
        if retry_after <= 0:
            user.password_reset_attempts = 0  # fresh code => reset the lockout counter
            _issue_and_send_code(user, purpose="user_reset")  # commits internally
        # Bind this reset session to the account regardless of cooldown, so a
        # user who already has a valid code can still proceed to verify it.
        session[_RESET_UID_KEY] = str(user.id)
        session.pop(_RESET_TOKEN_KEY, None)

    return generic_ok, 200


@api_bp.route("/verify_reset", methods=["POST"])
@_limiter.limit("10 per minute")
def verify_reset():
    """Verify the 6-digit reset code for the session-bound account.

    Identity comes from the server session (set during initiation), not the
    request, so a code can only ever be tested against the account that asked
    for it. The code is single-use (cleared on success) and brute-force-limited
    (cleared after PASSWORD_RESET_MAX_ATTEMPTS wrong tries), with a short
    PASSWORD_RESET_CODE_EXPIRY_MINUTES window.
    """
    data = request.json or {}
    code = str(data.get("token", "")).strip()

    user = _resolve_reset_user()
    if not user or not code:
        return error_response("Sesi reset tidak valid atau telah berakhir", reason="invalid_session")

    if not user.password_reset_code_hash:
        return error_response("Kode reset tidak berlaku. Minta kode baru.", reason="invalid_token")

    expiry_seconds = int(current_app.config.get("PASSWORD_RESET_CODE_EXPIRY_MINUTES", 10)) * 60
    ok, reason = verification_service.verify_token(
        code, user.email, user.password_reset_sent_at,
        code_hash=user.password_reset_code_hash, expiry_seconds=expiry_seconds,
    )

    if not ok:
        max_attempts = int(current_app.config.get("PASSWORD_RESET_MAX_ATTEMPTS", 5))
        user.password_reset_attempts = (user.password_reset_attempts or 0) + 1
        locked = user.password_reset_attempts >= max_attempts
        if locked:
            # Invalidate the code entirely so it can't be brute-forced further.
            user.password_reset_code_hash = None
            user.password_reset_sent_at = None
        db.session.commit()
        if locked:
            return error_response("Terlalu banyak percobaan. Minta kode baru.", reason="locked")
        return error_response(
            "Kode tidak valid" if reason == "invalid" else "Kode kedaluwarsa",
            reason=f"{reason}_token",
        )

    # Success: consume the code (single-use) and reset the lockout counter. We
    # keep password_reset_sent_at so the signed token below stays bound to it;
    # both are cleared once the reset actually completes.
    user.password_reset_code_hash = None
    user.password_reset_attempts = 0
    db.session.commit()

    reset_token = verification_service.generate_signed_token(
        user.email, salt="password-reset", sent_at=user.password_reset_sent_at
    )
    session[_RESET_TOKEN_KEY] = reset_token
    return jsonify({"success": True, "reset_token": reset_token}), 200


@api_bp.route("/reset_password", methods=["POST"])
@_limiter.limit("20 per minute")
def reset_password_public():
    """Final step: verify the session-bound signed token + save one biometric
    sample under the new password. Identity and token are read from the session,
    never the request body. On completion the reset credentials are wiped and
    ``session_token_version`` is bumped, killing every pre-existing session.
    """
    data = request.json or {}
    events = data.get("events")
    sample_count = int(data.get("sample_count") or 0)

    user = _resolve_reset_user()
    reset_token = session.get(_RESET_TOKEN_KEY)
    if not user or not reset_token or not events:
        return error_response("Sesi reset tidak valid atau telah berakhir", reason="invalid_session")

    # 1. Validate the signed token (bound to email + password_reset_sent_at).
    ok, reason = verification_service.verify_signed_token(
        reset_token, user.email, user.password_reset_sent_at, salt="password-reset"
    )
    if not ok:
        return error_response("Token reset tidak valid", reason=f"{reason}_token")

    username = user.username

    # 2. Process keystroke events
    from .helpers import process_events
    result = process_events(events, username)
    if result["status"] != "success":
        return error_response(result.get("msg", "Gagal memproses data ketikan"))

    features = result["features"]
    real_pass = result.get("real_password_string")

    if not real_pass:
        return error_response("Password master tidak ditemukan dalam sampel")

    # 3. Clear old enrollment + trained model on the FIRST sample of the reset
    # flow so the count restarts from 0 and the next login retrains against the
    # new keystroke rhythm (the old model fingerprinted the previous password —
    # keeping it would lock the user out).
    if sample_count == 1:
        from app.models import UsersVector, UserMLModel
        from sqlalchemy import delete
        db.session.execute(delete(UsersVector).where(UsersVector.username == username))
        db.session.execute(delete(UserMLModel).where(UserMLModel.user_id == user.id))
        db.session.commit()

    # 4. Update password & save sample (consolidated helper)
    user.set_password(real_pass)

    # Enrichment for audit
    strength = calculate_password_strength(real_pass)
    features["password_strength"] = strength["strength"]

    _, save_err = save_biometric_sample(username, user.id, features, result.get("password_hash"))
    if save_err:
        return save_err

    db.session.commit()

    new_status = get_biometric_service().get_enrollment_status(username)
    target = int(current_app.config.get("RECOMMENDED_SAMPLES", 10))

    # 5. On completion: invalidate the reset credentials so the code/token can
    # never be replayed, and bump session_token_version to evict every existing
    # session (defense against a stale/stolen session surviving the reset).
    if new_status["ready_for_login"]:
        user.password_reset_code_hash = None
        user.password_reset_sent_at = None
        user.password_reset_attempts = 0
        user.session_token_version = (user.session_token_version or 0) + 1
        db.session.commit()
        _clear_reset_session()

    return jsonify({
        "status": "success",
        "message": "Sample reset tersimpan",
        "progress": {
            "current": new_status["count"],
            "target": target,
            "complete": new_status["ready_for_login"],
        },
    }), 200


@api_bp.route("/resend_verification", methods=["POST"])
@_limiter.limit("3 per minute;20 per hour")
def resend_verification():
    """Resend code with rate limiting (limiter applied via app.py or globally)."""
    data = request.json or {}
    username = data.get("username")

    user = _fetch_user(username)
    if not user or not user.email:
        return error_response("User atau email tidak ditemukan")

    retry_after = _seconds_until_reissue_allowed(user, purpose="email_verify")
    if retry_after > 0:
        return _cooldown_response(retry_after)

    if _issue_and_send_code(user):
        return jsonify({"success": True, "message": "Email verifikasi dikirim ulang"}), 200
    return error_response("Gagal mengirim email", status_code=500)
