"""
Email verification, password-reset verification, and resend endpoints.
"""

from __future__ import annotations

import traceback
from datetime import datetime, timezone
from typing import Optional


from flask import current_app, jsonify, request
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
    """Send a password-reset code to user email.

    Per-user cooldown enforced server-side via `password_reset_sent_at` so the
    endpoint cannot be spammed even when the per-IP Flask-Limiter is bypassed
    (rotated IPs, disabled limiter, etc.).
    """
    data = request.json or {}
    username = data.get("username")
    if not username:
        return error_response("Username diperlukan")

    user = _fetch_user(username)
    if not user:
        return error_response("User tidak ditemukan", status_code=404)
    if not user.email:
        return error_response("Email tidak terdaftar di akun ini")

    retry_after = _seconds_until_reissue_allowed(user, purpose="user_reset")
    if retry_after > 0:
        return _cooldown_response(retry_after)

    if _issue_and_send_code(user, purpose="user_reset"):
        return jsonify({"success": True, "message": "Email verifikasi reset terkirim"}), 200
    return error_response("Gagal mengirim email", status_code=500)


@api_bp.route("/verify_reset", methods=["POST"])
@_limiter.limit("10 per minute")
def verify_reset():
    """Verify reset code and return a signed token for the public reset flow."""
    data = request.json or {}
    username = data.get("username")
    token = str(data.get("token", "")).strip()
    if not username or not token:
        return error_response("Data tidak lengkap")

    user = _fetch_user(username)
    if not user:
        return error_response("User tidak ditemukan", status_code=404)

    ok, reason = verification_service.verify_token(
        token, user.email, user.password_reset_sent_at, 
        code_hash=user.password_reset_code_hash
    )

    if not ok:
        return error_response(
            "Token tidak valid" if reason == "invalid" else "Token kadaluarsa",
            reason=f"{reason}_token"
        )

    # Issue a signed token for the next step (keystroke-based reset)
    reset_token = verification_service.generate_signed_token(
        user.email, salt="password-reset", sent_at=user.password_reset_sent_at
    )
    return jsonify({"success": True, "reset_token": reset_token}), 200


@api_bp.route("/reset_password", methods=["POST"])
@_limiter.limit("5 per minute")
def reset_password_public():
    """Final step of password reset: verify signed token + save biometric sample."""
    data = request.json or {}
    username = data.get("username")
    reset_token = data.get("reset_token")
    events = data.get("events")
    sample_count = int(data.get("sample_count") or 0)

    if not username or not reset_token or not events:
        return error_response("Data tidak lengkap")

    user = _fetch_user(username)
    if not user:
        return error_response("User tidak ditemukan", status_code=404)

    # 1. Validate signed token
    ok, reason = verification_service.verify_signed_token(
        reset_token, user.email, user.password_reset_sent_at, salt="password-reset"
    )
    if not ok:
        return error_response("Token reset tidak valid", reason=f"{reason}_token")

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
    # flow so the dashboard count restarts from 0 and the next login retrains
    # against the new keystroke rhythm (the old model fingerprinted the
    # previous password — keeping it would lock the user out).
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
    # Mirror the register flow: the UI re-enrolls 10 samples (matches MIN_ENROLLMENT_SAMPLES)
    target = int(current_app.config.get("RECOMMENDED_SAMPLES", 10))
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
