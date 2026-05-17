"""
Email verification, password-reset verification, and resend endpoints.
"""

from __future__ import annotations

import traceback
from datetime import datetime, timezone
from typing import Optional


from flask import jsonify, request
from sqlalchemy import select

from app.models import AdminAudit, User, db
from app.services.email_service import email_service
from app.services.verification_service import verification_service
from app.utils.password_strength import calculate_password_strength

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


def _issue_and_send_code(user, purpose: str = None):
    """Generate, persist, and send a verification code."""
    code = verification_service.generate_6_digit_code()
    sent_at = datetime.now(timezone.utc)
    
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
@_limiter.limit("5 per minute")
def send_verification():
    """Send a verification code to user email. Creates user if needed."""
    data = request.json or {}
    username = data.get("username")
    email = data.get("email")

    if not username or not email:
        return error_response("Data tidak lengkap")

    user = _fetch_user(username)
    created_new = False
    if not user:
        user = User(username=username, email=email, email_verified=False)
        db.session.add(user)
        db.session.commit()
        created_new = True

    if user.email != email:
        return error_response("Email tidak sesuai dengan akun")

    if _issue_and_send_code(user):
        return jsonify({"success": True, "message": "Email verifikasi terkirim", "created": created_new}), 200
    return error_response("Gagal mengirim email", status_code=500)


@api_bp.route("/send_reset_verification", methods=["POST"])
@_limiter.limit("5 per minute")
def send_reset_verification():
    """Send a password-reset code to user email."""
    data = request.json or {}
    username = data.get("username")
    if not username:
        return error_response("Username diperlukan")

    user = _fetch_user(username)
    if not user:
        return error_response("User tidak ditemukan", status_code=404)
    if not user.email:
        return error_response("Email tidak terdaftar di akun ini")

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

    # 3. Clear old enrollment on FIRST sample of reset
    if get_biometric_service().get_enrollment_status(username)["count"] == 0:
        from app.models import EnrollmentVector
        from sqlalchemy import delete
        db.session.execute(delete(EnrollmentVector).where(EnrollmentVector.username == username))
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
    return jsonify({
        "status": "success",
        "message": "Sample reset tersimpan",
        "progress": {
            "current": new_status["count"],
            "target": 20,
            "complete": new_status["ready_for_login"],
        },
    }), 200


@api_bp.route("/resend_verification", methods=["POST"])
@_limiter.limit("5 per minute")
def resend_verification():
    """Resend code with rate limiting (limiter applied via app.py or globally)."""
    data = request.json or {}
    username = data.get("username")
    
    user = _fetch_user(username)
    if not user or not user.email:
        return error_response("User atau email tidak ditemukan")

    if _issue_and_send_code(user):
        return jsonify({"success": True, "message": "Email verifikasi dikirim ulang"}), 200
    return error_response("Gagal mengirim email", status_code=500)
