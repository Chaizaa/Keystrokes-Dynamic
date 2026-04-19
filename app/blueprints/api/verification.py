"""
Email verification, password-reset verification, and resend endpoints.

Routes
------
POST /api/verify_email
POST /api/send_verification
POST /api/send_reset_verification
POST /api/verify_reset
POST /api/reset_password          (public – keystroke-based reset before login)
POST /api/resend_verification
"""

import json
import re
import secrets
import traceback
from datetime import datetime, timedelta, timezone

from flask import jsonify, request
from werkzeug.security import generate_password_hash

from app.models import EnrollmentVector, User, db
from app.models import db as sqlalchemy_db
from app.services.email_service import email_service
from app.utils.password_strength import calculate_password_strength

from ._shared import api_bp, get_biometric_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitize_token(raw: str) -> str:
    """Strip whitespace and extract token-like substring from pasted input."""
    token = raw.strip()
    token = "".join(token.split())
    if len(token) > 72 and not re.fullmatch(r"\d{6}", token):
        m = re.search(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", token)
        if m:
            return m.group(0)
        token = token.strip("\"'<>[]()")
    return token


def _fetch_user(username: str):
    from sqlalchemy import select
    return db.session.execute(select(User).where(User.username == username)).scalars().first()


def _verify_token_with_fallback(token, email, sent_at, *, code_hash=None, salt=None):
    """Call email_service.verify_token with backward-compatible fallback."""
    kwargs = {}
    if code_hash is not None:
        kwargs["code_hash"] = code_hash
    if salt is not None:
        kwargs["salt"] = salt

    try:
        return email_service.verify_token(token, email, sent_at, **kwargs)
    except TypeError:
        return email_service.verify_token(token, email, sent_at)


def _is_email_verification_expired(user) -> bool:
    """Return True when email verification token has exceeded configured expiry."""
    try:
        from flask import current_app

        expiry_hours = current_app.config.get("EMAIL_VERIFICATION_EXPIRY_HOURS", 1)
        sent_at = user.email_verification_sent_at
        if sent_at:
            if sent_at.tzinfo is None:
                sent_at = sent_at.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) > (sent_at + timedelta(hours=int(expiry_hours)))
    except Exception as exc:
        print("[DEBUG] verify_email expiry check failed:", exc)

    return False


def _generate_6_digit_code() -> str:
    """Generate a zero-padded six-digit one-time code."""
    return str(secrets.randbelow(10**6)).zfill(6)


def _issue_email_verification_code(user):
    """Set verification code fields on user and return generated code."""
    sent_at = datetime.now(timezone.utc)
    code = _generate_6_digit_code()
    user.email_verification_sent_at = sent_at
    user.email_verification_code_hash = generate_password_hash(code)
    return code


def _send_email_verification_code(user):
    """Persist and send a new email verification code."""
    code = _issue_email_verification_code(user)
    db.session.commit()
    return email_service.send_verification_email(user, code)


def _send_password_reset_code(user):
    """Persist and send a password-reset verification code."""
    sent_at = datetime.now(timezone.utc)
    code = _generate_6_digit_code()
    user.password_reset_code_hash = generate_password_hash(code)
    user.password_reset_sent_at = sent_at
    db.session.commit()
    email_service.send_verification_email(user, code, purpose="user_reset")


def _process_reset_events(username, events):
    """Process reset keystroke events and return extracted data."""
    import app.blueprints.api as api_mod

    result = api_mod.process_web_events(events, username)
    if result["status"] != "success":
        return None, None, None, (
            jsonify({"status": "error", "message": "Failed to process keystroke data"}),
            400,
        )

    features = result["features"]
    real_pass = result.get("real_password_string")
    password_hash = result.get("password_hash")

    if not real_pass:
        return None, None, None, (
            jsonify({"status": "error", "message": "Master password not provided in sample"}),
            400,
        )

    return features, real_pass, password_hash, None


def _clear_enrollment_if_needed(username):
    """Clear old enrollment vectors only on first reset sample."""
    enrollment_status = get_biometric_service().get_enrollment_status(username)
    enrollment_count = enrollment_status["count"]
    if enrollment_count == 0:
        try:
            from sqlalchemy import delete as sa_delete

            db.session.execute(sa_delete(EnrollmentVector).where(EnrollmentVector.username == username))
            db.session.commit()
        except Exception:
            pass


def _set_user_password_for_reset(user, real_pass, username):
    """Set and persist the new user password for reset flow."""
    try:
        user.set_password(real_pass)
        db.session.commit()
        return None
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] Failed to set password during reset for {username}: {e}")
        return jsonify({"status": "error", "message": "Unable to set password"}), 500


def _save_reset_enrollment_sample(username, user, features, password_hash):
    """Persist one enrollment sample generated during password reset."""
    try:
        from app.models import AdminAudit

        uid = getattr(user, "id", None)
        if uid is not None:
            features["user_id"] = int(uid)

        ev = EnrollmentVector(username=username, user_id=uid, event_type="enrollment")
        ev.timestamp = datetime.now(timezone.utc).isoformat()
        ev.total_duration = features.get("total_duration")
        ev.typing_speed = features.get("typing_speed")

        # Raw timing vectors
        for vec_name in ("H", "DD", "UD", "UU", "DU"):
            setattr(ev, f"{vec_name}_vector", json.dumps(features.get(f"{vec_name}_vector", [])))

        # Flat per-vector statistics (mean, std, min, max, cv)
        for prefix in ("H", "DD", "UD", "UU", "DU"):
            for stat in ("mean", "std", "min", "max", "cv"):
                col = f"{prefix}_{stat}"
                val = features.get(col)
                if val is not None:
                    setattr(ev, col, val)

        if password_hash:
            ev.password_hash = password_hash

        sqlalchemy_db.session.add(ev)
        sqlalchemy_db.session.commit()

        AdminAudit.log(
            action=AdminAudit.ACTION_ENROLLED,
            user_id=uid,
            username=username,
            details={
                "quality_label": features.get("quality_label"),
                "password_strength": features.get("password_strength"),
            },
        )
        db.session.commit()
        return None

    except Exception as e:
        print(f"[ERROR] reset_password save sample: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": "Database error saving sample"}), 500


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@api_bp.route("/verify_email", methods=["POST"])
def verify_email():
    """Verify a user's email using the token or 6-digit code sent via email."""
    try:
        data = request.json or {}
        username = data.get("username")
        token = data.get("token")
        if not username or not token:
            return jsonify({"success": False, "message": "Incomplete data",
                            "error_code": "invalid_input"}), 400

        token = _sanitize_token(str(token))
        user = _fetch_user(username)
        if not user:
            return jsonify({"success": False, "message": "User not found",
                            "error_code": "user_not_found"}), 404

        if _is_email_verification_expired(user):
            return jsonify({"success": False, "message": "Token expired",
                            "error_code": "expired_token"}), 400

        ok, reason = _verify_token_with_fallback(
            token,
            user.email,
            user.email_verification_sent_at,
            code_hash=user.email_verification_code_hash,
        )

        if not ok:
            if reason == "expired":
                return jsonify({"success": False, "message": "Token kadaluarsa",
                                "error_code": "expired_token"}), 400
            return jsonify({"success": False, "message": "Invalid token",
                            "error_code": "invalid_token"}), 400

        try:
            if user.email_verification_code_hash:
                user.email_verification_code_hash = None
        except Exception:
            pass
        user.email_verified = True
        db.session.commit()
        return jsonify({"success": True, "message": "Email verified"}), 200

    except Exception as e:
        print(f"[ERROR] verify_email: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


@api_bp.route("/send_verification", methods=["POST"])
def send_verification():
    """Send a 6-digit verification code to the user's email.
    Creates a provisional user row if none exists yet.
    """
    try:
        data = request.json or {}
        username = data.get("username")
        email = data.get("email")
        if not username or not email:
            return jsonify({"success": False, "message": "Incomplete data"}), 400

        user = _fetch_user(username)
        created_new = False
        if not user:
            try:
                user = User(username=username, email=email, email_verified=False)
                db.session.add(user)
                db.session.commit()
                created_new = True
            except Exception as e:
                db.session.rollback()
                print(f"[ERROR] Failed to create provisional user: {e}")
                return jsonify({"success": False,
                                "message": "Failed to create user for verification"}), 500

        if user.email and email and user.email != email:
            return jsonify({"success": False, "message": "Email mismatch with account"}), 400
        if not user.email and email:
            user.email = email

        try:
            _send_email_verification_code(user)
            print(f"[INFO] Verification email sent to {user.email}")
            return jsonify({"success": True, "message": "Verification email sent",
                            "created": created_new}), 200
        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] Failed to send verification email: {e}")
            return jsonify({"success": False, "message": "Failed to send email"}), 500

    except Exception as e:
        print(f"[ERROR] send_verification: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


@api_bp.route("/send_reset_verification", methods=["POST"])
def send_reset_verification():
    """Send a password-reset code to the user's email."""
    try:
        data = request.json or {}
        username = data.get("username")
        if not username:
            return jsonify({"success": False, "message": "Data tidak lengkap"}), 400

        user = _fetch_user(username)
        if not user:
            return jsonify({"success": False, "message": "User tidak ditemukan"}), 404
        if not user.email:
            return jsonify({"success": False, "message": "No email set on account"}), 400

        try:
            _send_password_reset_code(user)
            return jsonify({"success": True, "message": "Verification email sent"}), 200
        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] Failed to send reset verification email: {e}")
            return jsonify({"success": False, "message": "Failed to send email"}), 500

    except Exception as e:
        print(f"[ERROR] send_reset_verification: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


@api_bp.route("/verify_reset", methods=["POST"])
def verify_reset():
    """Verify reset code/token and return a signed reset token for the client."""
    try:
        data = request.json or {}
        username = data.get("username")
        token = data.get("token")
        if not username or not token:
            return jsonify({"success": False, "message": "Data tidak lengkap",
                            "error_code": "invalid_input"}), 400

        user = _fetch_user(username)
        if not user:
            return jsonify({"success": False, "message": "User not found"}), 404

        ok, reason = _verify_token_with_fallback(
            token,
            user.email,
            user.password_reset_sent_at,
            code_hash=user.password_reset_code_hash,
        )

        if not ok:
            if reason == "expired":
                return jsonify({"success": False, "message": "Token expired",
                                "error_code": "expired_token"}), 400
            return jsonify({"success": False, "message": "Invalid token",
                            "error_code": "invalid_token"}), 400

        try:
            reset_token = email_service.generate_token(
                user.email, salt="password-reset", sent_at=user.password_reset_sent_at)
            return jsonify({"success": True, "reset_token": reset_token}), 200
        except Exception as e:
            print(f"[ERROR] Failed to generate reset token: {e}")
            return jsonify({"success": False, "message": "Server error generating token"}), 500

    except Exception as e:
        print(f"[ERROR] verify_reset: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


from app import limiter as _limiter  # noqa: E402 (after blueprint definition)


@api_bp.route("/reset_password", methods=["POST"])
@_limiter.limit("10 per hour")
def reset_password_public():
    """Public keystroke-based password reset (before login).
    Expects JSON: {username, reset_token, events}
    """
    try:
        data = request.json or {}
        username = (data.get("username") or "").strip()
        reset_token = data.get("reset_token")
        events = data.get("events")

        if not username or not reset_token or not events:
            return jsonify({"status": "error", "message": "Data tidak lengkap"}), 400

        user = _fetch_user(username)
        if not user:
            return jsonify({"status": "error", "message": "User tidak ditemukan"}), 404

        # Validate the signed reset token
        ok, reason = _verify_token_with_fallback(
            reset_token,
            user.email,
            user.password_reset_sent_at,
            salt="password-reset",
        )

        if not ok:
            if reason == "expired":
                return jsonify({"status": "error", "message": "Reset token expired",
                                "error_code": "expired_token"}), 400
            return jsonify({"status": "error", "message": "Invalid reset token",
                            "error_code": "invalid_token"}), 400

        # Process keystroke events FIRST — before any DB mutation
        features, real_pass, password_hash, process_error = _process_reset_events(username, events)
        if process_error:
            return process_error

        # Weak password: log advisory only — do NOT block reset (UI already warns)
        strength_result = calculate_password_strength(real_pass)
        if strength_result["score"] < 0.5:
            print(f"[WARN] reset_password: weak password for '{username}' "
                  f"(strength={strength_result['strength']}, "
                  f"score={strength_result['score']:.2f})")

        # Only on the FIRST sample: clear old enrollment so this is a fresh re-enrollment
        _clear_enrollment_if_needed(username)

        # Persist the new password
        set_password_error = _set_user_password_for_reset(user, real_pass, username)
        if set_password_error:
            return set_password_error

        # Save enrollment sample with full feature data (matches enrollment.py)
        save_error = _save_reset_enrollment_sample(username, user, features, password_hash)
        if save_error:
            return save_error

        new_status = get_biometric_service().get_enrollment_status(username)
        return jsonify({
            "status": "success",
            "message": "Sample saved",
            "progress": {
                "current": new_status["count"],
                "target": 20,
                "complete": new_status["ready_for_login"],
            },
        }), 200

    except Exception as e:
        print(f"[ERROR] reset_password (public): {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@api_bp.route("/resend_verification", methods=["POST"])
@_limiter.limit("3 per 15 minutes")
def resend_verification():
    """Resend a verification code (rate-limited)."""
    try:
        data = request.json or {}
        username = data.get("username")
        if not username:
            return jsonify({"success": False, "message": "Username required",
                            "error_code": "invalid_input"}), 400

        user = _fetch_user(username)
        if not user:
            return jsonify({"success": False, "message": "User not found",
                            "error_code": "user_not_found"}), 404
        if not user.email:
            return jsonify({"success": False, "message": "No email on account",
                            "error_code": "no_email"}), 400

        try:
            sent = _send_email_verification_code(user)
            if not sent:
                return jsonify({"success": False, "message": "Failed to send email"}), 500
            return jsonify({"success": True, "message": "Verification email resent"}), 200
        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] resend_verification: {e}")
            traceback.print_exc()
            return jsonify({"success": False,
                            "message": "Failed to resend verification"}), 500

    except Exception as e:
        print(f"[ERROR] resend_verification (outer): {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500
