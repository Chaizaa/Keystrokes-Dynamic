"""
API Blueprint - RESTful API endpoints for biometric authentication
"""

import json
<<<<<<< HEAD:app/blueprints/_archive/api_legacy.py
import re
import secrets
=======
import secrets

>>>>>>> chaizaa/habib_api:app/blueprints/api.py
import traceback
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, jsonify, request, session
from flask_login import current_user, login_required, logout_user
from sqlalchemy import select
from werkzeug.security import generate_password_hash

from app import limiter  # Import rate limiter
from app.database import Database
<<<<<<< HEAD:app/blueprints/_archive/api_legacy.py
from app.models import AdminAudit, EnrollmentVector, KeystrokeVector, User, db
from app.services import AuthService, BiometricService  # Import service layer
=======
from app.models import User, db  # Import User model and db
from app.services import APIKeyService, AuthService, BiometricService  # Import service layer
>>>>>>> chaizaa/habib_api:app/blueprints/api.py
from app.services.email_service import email_service
from app.utils.keystroke_processor import assess_sample_quality, process_web_events
from app.utils.password_strength import (
    calculate_password_strength,
    get_strength_label,
)

api_bp = Blueprint("api", __name__)

# Initialize database (legacy - being phased out)
db_manager = Database()

# Initialize services (new architecture)
auth_service = AuthService()
# Pass the legacy db manager to BiometricService so it can read enrollment samples
biometric_service = BiometricService(db=db_manager)


def _get_client_ip():
    """Resolve client IP, preferring X-Forwarded-For when behind a proxy."""
    forwarded_for = (request.headers.get("X-Forwarded-For") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.remote_addr


def _extract_partner_api_key():
    """Extract API key from Authorization header or X-API-Key fallback."""
    auth_header = (request.headers.get("Authorization") or "").strip()
    if auth_header:
        if auth_header.lower().startswith("bearer "):
            return auth_header.split(" ", 1)[1].strip()
        return auth_header

    return (request.headers.get("X-API-Key") or "").strip()


def _authenticate_partner_api_request():
    """Validate API key, origin policy, and per-key quota for partner endpoints."""
    provided_key = _extract_partner_api_key()
    is_valid, api_key, error_message = APIKeyService.verify_api_key(provided_key)
    if not is_valid:
        lowered_error = (error_message or "").lower()
        status_code = 401
        if "expired" in lowered_error or "inactive" in lowered_error:
            status_code = 403

        return None, (
            jsonify(
                {
                    "success": False,
                    "message": error_message or "Unauthorized",
                    "error_code": "INVALID_API_KEY",
                }
            ),
            status_code,
        )

    origin = (request.headers.get("Origin") or "").strip()
    if not origin:
        origin = (request.headers.get("Referer") or "").strip()

    if not APIKeyService.check_origin_allowed(api_key, origin):
        return None, (
            jsonify(
                {
                    "success": False,
                    "message": "Request origin is not allowed for this API key",
                    "error_code": "ORIGIN_NOT_ALLOWED",
                }
            ),
            403,
        )

    is_allowed, remaining_quota, error_message = APIKeyService.check_rate_limit(api_key)
    if not is_allowed:
        return None, (
            jsonify(
                {
                    "success": False,
                    "message": error_message,
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "remaining_quota": 0,
                }
            ),
            429,
        )

    return (
        {
            "api_key": api_key,
            "origin": origin or None,
            "client_ip": _get_client_ip(),
            "user_agent": request.headers.get("User-Agent", "Unknown"),
            "remaining_quota": remaining_quota,
        },
        None,
    )


def _normalize_numeric_vector(raw_vector, field_name):
    """Normalize vector values to floats and validate payload shape."""
    if raw_vector is None:
        return []
    if not isinstance(raw_vector, list):
        raise ValueError(f"{field_name} must be an array of numbers")

    normalized = []
    for value in raw_vector:
        try:
            normalized.append(float(value))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} contains non-numeric value") from exc
    return normalized


def _build_partner_features(payload, username):
    """Build feature vectors either from raw events or directly provided vectors."""
    events = payload.get("events")
    if events is not None:
        if not isinstance(events, list) or not events:
            return None, None, None, "events must be a non-empty array"
        processed = process_web_events(events, username)
        if processed.get("status") != "success":
            return None, None, None, processed.get("msg", "Failed to process keystroke events")

        features = processed.get("features") or {}
        return (
            features,
            processed.get("real_password_string"),
            processed.get("password_hash"),
            None,
        )

    raw_features = payload.get("features") if isinstance(payload.get("features"), dict) else {}
    merged = dict(raw_features)

    for key in ("H_vector", "DD_vector", "UD_vector", "UU_vector", "DU_vector"):
        if key in payload and key not in merged:
            merged[key] = payload.get(key)

    try:
        features = {
            "H_vector": _normalize_numeric_vector(merged.get("H_vector"), "H_vector"),
            "DD_vector": _normalize_numeric_vector(merged.get("DD_vector"), "DD_vector"),
            "UD_vector": _normalize_numeric_vector(merged.get("UD_vector"), "UD_vector"),
            "UU_vector": _normalize_numeric_vector(merged.get("UU_vector"), "UU_vector"),
            "DU_vector": _normalize_numeric_vector(merged.get("DU_vector"), "DU_vector"),
        }
    except ValueError as exc:
        return None, None, None, str(exc)

    if not features["H_vector"] or not features["DD_vector"]:
        return None, None, None, "events or H_vector/DD_vector are required"

    password = payload.get("password") if isinstance(payload.get("password"), str) else None
    password_hash = (
        payload.get("password_hash") if isinstance(payload.get("password_hash"), str) else None
    )
    return features, password, password_hash, None


def _safe_parse_vector(raw_value):
    """Parse serialized vector values from database rows."""
    if raw_value is None:
        return []
    if isinstance(raw_value, list):
        return raw_value
    if isinstance(raw_value, tuple):
        return list(raw_value)
    if isinstance(raw_value, str):
        try:
            parsed = json.loads(raw_value)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass

        try:
            import ast

            parsed = ast.literal_eval(raw_value)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass

    return []


def _load_partner_enrollment_templates(username):
    """Load enrollment templates from SQLAlchemy-backed tables for partner verification."""
    from sqlalchemy import select

    from app.models import EnrollmentVector, KeystrokeVector

    templates = []

    enrollment_rows = (
        db.session.execute(
            select(EnrollmentVector)
            .where(EnrollmentVector.username == username)
            .order_by(EnrollmentVector.id.desc())
        )
        .scalars()
        .all()
    )

    for row in enrollment_rows:
        h_vector = _safe_parse_vector(getattr(row, "H_vector", None))
        dd_vector = _safe_parse_vector(getattr(row, "DD_vector", None))
        if not h_vector or not dd_vector:
            continue
        templates.append(
            {
                "H_vector": h_vector,
                "DD_vector": dd_vector,
                "UD_vector": _safe_parse_vector(getattr(row, "UD_vector", None)),
            }
        )

    if templates:
        return templates

    vector_rows = (
        db.session.execute(
            select(KeystrokeVector)
            .where(
                KeystrokeVector.username == username,
                KeystrokeVector.event_type == "enrollment",
                KeystrokeVector.is_successful.is_(True),
            )
            .order_by(KeystrokeVector.id.desc())
        )
        .scalars()
        .all()
    )

    for row in vector_rows:
        h_vector = _safe_parse_vector(getattr(row, "H_vector", None))
        dd_vector = _safe_parse_vector(getattr(row, "DD_vector", None))
        if not h_vector or not dd_vector:
            continue
        templates.append(
            {
                "H_vector": h_vector,
                "DD_vector": dd_vector,
                "UD_vector": _safe_parse_vector(getattr(row, "UD_vector", None)),
            }
        )

    return templates

# ============================================================================
# USERNAME VALIDATION
# ============================================================================


@api_bp.route("/verify_email", methods=["POST"])
def verify_email():
    """Verify a user's email using the token sent via email."""
    try:
        data = request.json or {}
        username = data.get("username")
        token = data.get("token")
        if not username or not token:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Incomplete data",
                        "error_code": "invalid_input",
                    }
                ),
                400,
            )

        # Normalize token input: trim whitespace and remove internal whitespace/newlines from pasted tokens
        try:
            token = token.strip()
            # Remove any whitespace characters (spaces, newlines) that might be introduced when copying
            token = "".join(token.split())
            # If user pasted a long string that contains surrounding punctuation (e.g., <token>, 'token')
            # try to extract a token-like substring (signed token usually contains a dot separator)
            import re

            if len(token) > 72 and not re.fullmatch(r"\d{6}", token):
                m = re.search(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", token)
                if m:
                    token = m.group(0)
                else:
                    # remove common wrapping characters
                    token = token.strip("\"'<>[]()")
        except Exception:
            pass
        from sqlalchemy import select

        user = db.session.execute(select(User).where(User.username == username)).scalars().first()
        if not user:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "User not found",
                        "error_code": "user_not_found",
                    }
                ),
                404,
            )

        # Check expiry
        try:
            from datetime import datetime, timedelta, timezone

            from flask import current_app

            expiry_hours = current_app.config.get("EMAIL_VERIFICATION_EXPIRY_HOURS", 1)
            sent_at = user.email_verification_sent_at
            if sent_at:
                # Normalize naive datetimes to UTC to avoid comparison errors
                try:
                    if sent_at.tzinfo is None:
                        sent_at = sent_at.replace(tzinfo=timezone.utc)
                except Exception:
                    pass
                if datetime.now(timezone.utc) > (sent_at + timedelta(hours=int(expiry_hours))):
                    return (
                        jsonify(
                            {
                                "success": False,
                                "message": "Token expired",
                                "error_code": "expired_token",
                            }
                        ),
                        400,
                    )
        except Exception as _e:
            # If timestamp parsing fails, continue and validate token normally
            print("[DEBUG] verify_email expiry check failed:", _e)

        # Verify token: accepts both a 6-digit numeric code (short-code flow)
        # and a signed 'email-verify' token.
        # Password-reset tokens (salt="password-reset") are intentionally NOT
        # accepted here; they are only valid at /api/reset_password.
        try:
            ok, reason = email_service.verify_token(
                token,
                user.email,
                user.email_verification_sent_at,
                code_hash=user.email_verification_code_hash,
            )
        except TypeError:
            # Backwards-compatible fallback for older monkeypatches
            ok, reason = email_service.verify_token(
                token, user.email, user.email_verification_sent_at
            )

        if not ok:
            # NOTE: intentionally do NOT fall back to salt="password-reset" here.
            # Admin reset tokens must only be accepted via /api/reset_password,
            # not via the email-verification endpoint.
            if reason == "expired":
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "Token kadaluarsa",
                            "error_code": "expired_token",
                        }
                    ),
                    400,
                )
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Invalid token",
                        "error_code": "invalid_token",
                    }
                ),
                400,
            )

        # Successful verification: clear short-code hash if present and mark verified
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
    """Send a verification token to the user's email. Expects JSON: {username, email}
    This can be called after enrollment completes to issue a token and email it to the user.
    """
    try:
        data = request.json or {}
        username = data.get("username")
        email = data.get("email")
        if not username or not email:
            return jsonify({"success": False, "message": "Incomplete data"}), 400
        # Resolve user; if not found, create a provisional user record so we can send verification
        from sqlalchemy import select

        user = db.session.execute(select(User).where(User.username == username)).scalars().first()
        created_new = False
        if not user:
            try:
                # Create a user row without password (will be set later during enrollment)
                user = User(username=username, email=email, email_verified=False)
                db.session.add(user)
                db.session.commit()
                created_new = True
            except Exception as e:
                db.session.rollback()
                print(f"[ERROR] Failed to create provisional user for verification: {e}")
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "Failed to create user for verification",
                        }
                    ),
                    500,
                )

        # Ensure email matches or set it
        if user.email and email and user.email != email:
            return (
                jsonify({"success": False, "message": "Email mismatch with account"}),
                400,
            )
        if not user.email and email:
            user.email = email

        # Save timestamp and send stateless token (or short code)
        try:
            sent_at = datetime.now(timezone.utc)
            user.email_verification_sent_at = sent_at
            # Generate a 6-digit numeric code and store its hash
            import secrets

            from werkzeug.security import generate_password_hash

            code = str(secrets.randbelow(10**6)).zfill(6)
            user.email_verification_code_hash = generate_password_hash(code)
            db.session.commit()
            # Send the short code in the email body
            email_service.send_verification_email(user, code)
            print(f"[INFO] Verification email sent to {user.email}")
            return (
                jsonify(
                    {
                        "success": True,
                        "message": "Verification email sent",
                        "created": created_new,
                    }
                ),
                200,
            )
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
    """Send a password-reset verification code to the user's email.
    Expects JSON: {username, email}
    """
    try:
        data = request.json or {}
        username = data.get("username")
        if not username:
            return jsonify({"success": False, "message": "Data tidak lengkap"}), 400

        from sqlalchemy import select

        user = db.session.execute(select(User).where(User.username == username)).scalars().first()
        if not user:
            return jsonify({"success": False, "message": "User tidak ditemukan"}), 404
        if not user.email:
            return (
                jsonify({"success": False, "message": "No email set on account"}),
                400,
            )

        try:
            sent_at = datetime.now(timezone.utc)
            import secrets

            from werkzeug.security import generate_password_hash

            code = str(secrets.randbelow(10**6)).zfill(6)
            # Write reset code to the dedicated password_reset_* columns so this
            # does not overwrite the email_verification_sent_at used by the
            # registration email-verification flow.
            user.password_reset_code_hash = generate_password_hash(code)
            user.password_reset_sent_at = sent_at
            db.session.commit()
            # Send email with purpose=user_reset so UI will redirect appropriately
            email_service.send_verification_email(user, code, purpose="user_reset")
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
    """Verify a reset code/token and return a signed reset token the client can use to submit new password samples.
    Expects JSON: {username, token}
    Returns: {success: True, reset_token: <signed-token>} on success.
    """
    try:
        data = request.json or {}
        username = data.get("username")
        token = data.get("token")
        if not username or not token:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Data tidak lengkap",
                        "error_code": "invalid_input",
                    }
                ),
                400,
            )
        from sqlalchemy import select

        user = db.session.execute(select(User).where(User.username == username)).scalars().first()
        if not user:
            return jsonify({"success": False, "message": "User not found"}), 404

        try:
            ok, reason = email_service.verify_token(
                token,
                user.email,
                user.password_reset_sent_at,
                code_hash=user.password_reset_code_hash,
            )
        except TypeError:
            ok, reason = email_service.verify_token(
                token, user.email, user.password_reset_sent_at
            )
        if not ok:
            if reason == "expired":
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "Token expired",
                            "error_code": "expired_token",
                        }
                    ),
                    400,
                )
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Invalid token",
                        "error_code": "invalid_token",
                    }
                ),
                400,
            )

        # Generate a signed reset token that the client must present when submitting reset samples
        try:
            reset_token = email_service.generate_token(
                user.email,
                salt="password-reset",
                sent_at=user.password_reset_sent_at,
            )
            return jsonify({"success": True, "reset_token": reset_token}), 200
        except Exception as e:
            print(f"[ERROR] Failed to generate reset token: {e}")
            return (
                jsonify({"success": False, "message": "Server error generating token"}),
                500,
            )

    except Exception as e:
        print(f"[ERROR] verify_reset: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


@api_bp.route("/reset_password", methods=["POST"])
@limiter.limit("10 per hour")
def reset_password_public():
    """Public reset endpoint to accept keystroke samples and the signed reset token.
    Expects JSON: {username, reset_token, events}
    Behaves similarly to registration sample saving but will set the new password on the user
    even if the account previously had a password. Existing enrollment data will be removed
    so this acts like a fresh re-enrollment.
    """
    try:
        data = request.json or {}
        username = (data.get("username") or "").strip()
        reset_token = data.get("reset_token")
        events = data.get("events")
        if not username or not reset_token or not events:
            return jsonify({"status": "error", "message": "Data tidak lengkap"}), 400

        from sqlalchemy import select

        user = db.session.execute(select(User).where(User.username == username)).scalars().first()
        if not user:
            return jsonify({"status": "error", "message": "User tidak ditemukan"}), 404

        # Verify signed reset token — read from the dedicated password_reset_sent_at
        # column so admin resets don't interfere with email verification state.
        ok, reason = email_service.verify_signed_token(
            reset_token,
            user.email,
            user.password_reset_sent_at,
            salt="password-reset",
        )
        if not ok:
            if reason == "expired":
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "Token expired",
                            "error_code": "expired_token",
                        }
                    ),
                    400,
                )
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Invalid reset token",
                        "error_code": "invalid_token",
                    }
                ),
                400,
            )

        # Delete existing enrollment data to start fresh
        try:
            db_manager.delete_enrollment_data(username)
        except Exception:
            # Ignore if legacy DB manager cannot delete; proceed
            pass

        # Process keystroke events
        result = process_web_events(events, username)
        if result["status"] != "success":
            return (
                jsonify({"status": "error", "message": "Failed to process keystroke data"}),
                400,
            )

        features = result["features"]
        real_pass = result.get("real_password_string")
        password_hash = result.get("password_hash")

        if not real_pass:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Master password not provided in sample",
                    }
                ),
                400,
            )

        # Enforce minimum strength on first sample
        strength_result = calculate_password_strength(real_pass)
        if strength_result["score"] < 0.5:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Password terlalu lemah",
                        "error_code": "WEAK_PASSWORD",
                        "strength": strength_result["strength"],
                    }
                ),
                400,
            )

        # Set new password on user
        try:
            user.set_password(real_pass)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] Failed to set new password during reset for {username}: {e}")
            return (
                jsonify({"status": "error", "message": "Unable to set password"}),
                500,
            )

        # Save enrollment sample as in register_sample
        try:
            from app.models import EnrollmentVector
            from app.models import db as sqlalchemy_db

            uid = getattr(user, "id", None)
            ev = EnrollmentVector(username=username, user_id=uid, event_type="enrollment")
            if "H_vector" in features:
                ev.H_vector = json.dumps(features["H_vector"])
            if "DD_vector" in features:
                ev.DD_vector = json.dumps(features["DD_vector"])
            if password_hash:
                ev.password_hash = password_hash

            sqlalchemy_db.session.add(ev)
            sqlalchemy_db.session.commit()
            # Audit: record enrollment event
            try:
                from app.models import AdminAudit

                audit = AdminAudit(
                    user_id=uid,
                    username=username,
                    action="enrollment",
                    details=json.dumps(
                        {
                            "quality_label": features.get("quality_label"),
                            "password_strength": features.get("password_strength"),
                        }
                    ),
                )
                sqlalchemy_db.session.add(audit)
                sqlalchemy_db.session.commit()
            except Exception:
                pass
        except Exception as e:
            print(f"[ERROR] reset_password save sample: {e}")
            traceback.print_exc()
            return (
                jsonify({"status": "error", "message": "Database error saving sample"}),
                500,
            )

        new_status = biometric_service.get_enrollment_status(username)
        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Sample saved",
                    "progress": {
                        "current": new_status["count"],
                        "target": 20,
                        "complete": new_status["ready_for_login"],
                    },
                }
            ),
            200,
        )

    except Exception as e:
        print(f"[ERROR] reset_password (public): {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@api_bp.route("/resend_verification", methods=["POST"])
@limiter.limit("3 per 15 minutes")
def resend_verification():
    """Resend a verification token to user's email (rate-limited).
    Expects JSON: {username} (email optional if already set on account)
    """
    try:
        data = request.json or {}
        username = data.get("username")
        if not username:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Username required",
                        "error_code": "invalid_input",
                    }
                ),
                400,
            )
        from sqlalchemy import select

        user = db.session.execute(select(User).where(User.username == username)).scalars().first()
        if not user:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "User not found",
                        "error_code": "user_not_found",
                    }
                ),
                404,
            )
        if not user.email:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "No email on account",
                        "error_code": "no_email",
                    }
                ),
                400,
            )
        try:
            sent_at = datetime.now(timezone.utc)
            user.email_verification_sent_at = sent_at
            # Generate short code and store hash
            import secrets

            from werkzeug.security import generate_password_hash

            code = str(secrets.randbelow(10**6)).zfill(6)
            user.email_verification_code_hash = generate_password_hash(code)
            db.session.commit()
            sent = email_service.send_verification_email(user, code)
            if not sent:
                return (
                    jsonify({"success": False, "message": "Failed to send email"}),
                    500,
                )
            return (
                jsonify({"success": True, "message": "Verification email resent"}),
                200,
            )
        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] resend_verification: {e}")
            traceback.print_exc()
            return (
                jsonify({"success": False, "message": "Failed to resend verification"}),
                500,
            )
    except Exception as e:
        print(f"[ERROR] resend_verification (outer): {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


@api_bp.route("/2fa/enroll", methods=["POST"])
def enroll_2fa():
    """Create a 2FA secret for the specified user and return the secret (for provisioning in tests)."""
    try:
        data = request.json or {}
        username = data.get("username")
        if not username:
            return jsonify({"success": False, "message": "Data tidak lengkap"}), 400
        from sqlalchemy import select

        user = db.session.execute(select(User).where(User.username == username)).scalars().first()
        if not user:
            return jsonify({"success": False, "message": "User tidak ditemukan"}), 404
        import pyotp

        secret = pyotp.random_base32()
        user.two_factor_secret = secret
        user.two_factor_enabled = False
        db.session.commit()
        return jsonify({"success": True, "secret": secret}), 200
    except Exception as e:
        print(f"[ERROR] enroll_2fa: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


@api_bp.route("/2fa/confirm", methods=["POST"])
def confirm_2fa():
    """Confirm a 2FA token and enable 2FA for the user if valid."""
    try:
        data = request.json or {}
        username = data.get("username")
        token = data.get("token")
        if not username or not token:
            return jsonify({"success": False, "message": "Data tidak lengkap"}), 400
        auth = AuthService()
        if not auth.verify_two_factor_token(username, token):
            return jsonify({"success": False, "message": "Token tidak valid"}), 400
        from sqlalchemy import select

        user = db.session.execute(select(User).where(User.username == username)).scalars().first()
        user.two_factor_enabled = True
        db.session.commit()
        return jsonify({"success": True, "message": "2FA diaktifkan"}), 200
    except Exception as e:
        print(f"[ERROR] confirm_2fa: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


@api_bp.route("/2fa/verify", methods=["POST"])
def verify_2fa():
    """Verify a 2FA token for a username (used after login flow)."""
    try:
        data = request.json or {}
        username = data.get("username")
        token = data.get("token")
        if not username or not token:
            return jsonify({"success": False, "message": "Data tidak lengkap"}), 400
        auth = AuthService()
        ok = auth.verify_two_factor_token(username, token)
        return jsonify({"success": ok}), (200 if ok else (jsonify({"success": False}), 400))
    except Exception as e:
        print(f"[ERROR] verify_2fa: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


@api_bp.route("/check_username", methods=["POST"])
@limiter.limit("10 per minute")  # Prevent username enumeration
def check_username():
    """
    Check username availability for registration or login
    Uses AuthService + BiometricService for validation
    """
    try:
        data = request.json
        username = data.get("username", "").strip()
        # Support email lookup: if identifier looks like an email, resolve to username
        try:
            if "@" in username:
                user_obj = auth_service.get_user_by_email(username)
                if user_obj:
                    username = user_obj.username
                else:
                    # No user with that email
                    return (
                        jsonify(
                            {
                                "exists": False,
                                "can_login": False,
                                "enrollment_complete": False,
                                "enrollment_count": 0,
                                "message": f"User {username} tidak ditemukan",
                            }
                        ),
                        200,
                    )
        except Exception:
            pass
        check_mode = data.get("mode", "register")

        if not username:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Username tidak boleh kosong",
                        "exists": False,
                        "enrollment_complete": False,
                        "enrollment_count": 0,
                    }
                ),
                400,
            )

        # Use AuthService to check availability
        availability = auth_service.check_username_availability(username)

        # Get enrollment status from BiometricService
        enrollment_status = biometric_service.get_enrollment_status(username)
        enrollment_count = enrollment_status["count"]

        login_ready = enrollment_status["ready_for_login"]  # 10+ samples

        print(f"[CHECK USERNAME] User: {username}, Mode: {check_mode}")
        print(f"  - Exists: {availability['exists']}, Enrollment: {enrollment_count}")

        # LOGIN MODE
        if check_mode == "login":
            if not availability["exists"]:
                return (
                    jsonify(
                        {
                            "exists": False,
                            "can_login": False,
                            "enrollment_complete": False,
                            "enrollment_count": 0,
                            "message": f"User {username} tidak ditemukan",
                        }
                    ),
                    200,
                )

            return (
                jsonify(
                    {
                        "exists": True,
                        "can_login": login_ready,
                        "enrollment_complete": login_ready,
                        "enrollment_count": enrollment_count,
                        "message": (
                            f"User {username} ditemukan"
                            if login_ready
                            else f"Enrollment belum lengkap ({enrollment_count}/20)"
                        ),
                    }
                ),
                200,
            )

        # REGISTER MODE - Use AuthService response
        # Status should be explicit: 'available', 'taken', or 'resumable' (partial registration)
        # Special case: if user row exists and enrollment is not complete (<=19), treat as resumable
        # This allows existing accounts with 0 samples to start/resume enrollment
        if availability.get("exists") and enrollment_count > 0 and enrollment_count < 20:
            status_str = "resumable"
        elif not availability["available"] and availability.get("reason") == "resumable":
            status_str = "resumable"
        elif not availability["available"]:
            status_str = "taken"
        else:
            status_str = "available"

        response_data = {
            "status": status_str,
            "available": availability["available"],
            "exists": availability["exists"],
            "message": availability["message"],
            "enrollment_count": enrollment_count,
            "is_retry": enrollment_count > 0,
        }

        # If we converted an existing user into a resumable flow, make message actionable
        if status_str == "resumable" and availability.get("exists"):
            response_data["message"] = (
                f"Resume registration: {enrollment_count}/20 samples collected"
            )

        # No need to send sample count details to frontend
        response_data["detail"] = ""

        return jsonify(response_data)

    except Exception as e:
        print(f"[ERROR] check_username: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================================
# REGISTRATION ENDPOINTS
# ============================================================================


@api_bp.route("/register_sample", methods=["POST"])
@limiter.limit("30 per minute")  # Rate limit: 30 enrollment samples per minute
def register_sample():
    """
    Register a single keystroke sample during enrollment
    """
    try:
        data = request.json
        username = (data.get("username") or "").strip()
        events = data.get("events")
        raw_email = data.get("email", None)
        # Accept null/None emails from client; only strip if it's a string
        if isinstance(raw_email, str):
            email = raw_email.strip() or None
        else:
            email = None

        if not events or not username:
            return jsonify({"status": "error", "message": "Data tidak lengkap"}), 400

        # Validate username
        validation = auth_service.validate_username(username)
        if not validation["valid"]:
            return jsonify({"status": "error", "message": validation["message"]}), 400

        # Check enrollment status
        enrollment_status = biometric_service.get_enrollment_status(username)
        enrollment_count = enrollment_status["count"]

        # Allow continuing enrollment up to 20 samples
        # Username availability was already validated at /check_username

        if enrollment_count > 0:
            print(
                f"[INFO] User '{username}' continuing registration (progress: {enrollment_count}/20)"
            )

        # Process keystroke events
        result = process_web_events(events, username)

        if result["status"] == "success":
            features = result["features"]
            features["username"] = username
            features["event_type"] = "enrollment"

            # Quality assessment
            quality = assess_sample_quality(features)
            features["quality_label"] = quality["quality_label"]
            features["quality_score"] = quality["quality_score"]

            # Password strength detection
            real_pass = result.get("real_password_string")
            password_hash = result.get("password_hash")

            if real_pass:
                strength_result = calculate_password_strength(real_pass)
                features["password_strength"] = strength_result["strength"]
                features["password_score"] = strength_result["score"]

                # Enforce minimum password strength (first sample only)
                # Enforce minimum password strength for initial enrollment.
                # `calculate_password_strength` returns a normalized score in [0, 1].
                # Require at least 'medium' strength (score >= 0.5) for initial account creation.
                if enrollment_count == 0 and strength_result["score"] < 0.5:
                    return (
                        jsonify(
                            {
                                "status": "error",
                                "message": "Password terlalu lemah",
                                "error_code": "WEAK_PASSWORD",
                                "strength": strength_result["strength"],
                            }
                        ),
                        400,
                    )

                # PASSWORD VALIDATION: Check if typed password matches master password
                if enrollment_count > 0:
                    # For subsequent samples (2-20), validate against existing password
                    user = auth_service.get_user_by_username(username)
                    if user:
                        # Check if password matches
                        if not user.check_password(real_pass):
                            return (
                                jsonify(
                                    {
                                        "status": "error",
                                        "message": "Incorrect password",
                                        "error_code": "PASSWORD_MISMATCH",
                                    }
                                ),
                                400,
                            )
                    else:
                        return (
                            jsonify({"status": "error", "message": "User tidak ditemukan"}),
                            404,
                        )

                # Save credentials using AuthService (first enrollment only)
                if enrollment_count == 0:
                    # If a user row already exists (existing account with 0 samples), don't try to create a new user
                    existing_user = auth_service.get_user_by_username(username)
                    if existing_user:
                        # If the existing user already has a password, verify it matches the typed password
                        has_password = bool(
                            getattr(existing_user, "password_hash", None)
                            or getattr(existing_user, "plain_password", None)
                        )
                        if has_password:
                            try:
                                valid_pwd = existing_user.check_password(real_pass)
                            except Exception:
                                valid_pwd = False

                            if not valid_pwd:
                                # If password mismatch, ask the client to retry with correct password
                                return (
                                    jsonify(
                                        {
                                            "status": "error",
                                            "message": "Incorrect password",
                                            "error_code": "PASSWORD_MISMATCH",
                                        }
                                    ),
                                    400,
                                )
                            else:
                                # Password matches — proceed and treat this as the first saved sample for the user
                                user = existing_user
                        else:
                            # Existing account has no password set (legacy/migration case)
                            # Allow setting password during first enrollment sample
                            try:
                                existing_user.set_password(real_pass)
                                db.session.commit()
                                user = existing_user
                                # Mark that we set a password on an existing account so the frontend can inform the user
                                password_event = "PASSWORD_SET_ON_EXISTING"
                            except Exception as e:
                                db.session.rollback()
                                print(
                                    f"[ERROR] Failed to set password for existing user {username}: {e}"
                                )
                                return (
                                    jsonify(
                                        {
                                            "status": "error",
                                            "message": "Unable to set password",
                                        }
                                    ),
                                    500,
                                )
                    else:
                        # No existing user row — create a new user account with password; email is optional
                        user_result = auth_service.create_user(username, real_pass, email=email)
                        if not user_result["success"]:
                            # Map specific error codes from AuthService to frontend-friendly payloads
                            err_payload = {
                                "status": "error",
                                "message": user_result.get("message", "Unable to create account"),
                            }
                            if user_result.get("error_code"):
                                err_payload["error_code"] = user_result["error_code"]
                            return jsonify(err_payload), 400

                        # Send verification email if email is provided
                        user = user_result.get("user")
                        # Audit: user registration
                        try:
                            from app.models import AdminAudit

                            if user:
                                a = AdminAudit(
                                    user_id=user.id,
                                    username=user.username,
                                    action="registered",
                                    details=json.dumps({"email": user.email}),
                                )
                                db.session.add(a)
                                db.session.commit()
                        except Exception:
                            pass
                        if user:
                            # Ensure future DB writers can map this enrollment to user
                            try:
                                features["user_id"] = int(user.id)
                            except Exception:
                                pass
                        if user and user.email and email and "@" in email:
                            # Use Session.get to fetch any latest DB state for user
                            user = db.session.get(User, user.id)
                            try:
                                sent_at = datetime.now(timezone.utc)
                                user.email_verification_sent_at = sent_at
                                db.session.commit()
                                try:
                                    token = email_service.generate_token(
                                        user.email, salt="email-verify", sent_at=sent_at
                                    )
                                except TypeError:
                                    token = email_service.generate_token(
                                        user.email, salt="email-verify"
                                    )
                                email_service.send_verification_email(user, token)
                                print(f"[INFO] Verification email sent to {user.email}")
                            except Exception as e:
                                print(f"[WARNING] Failed to send verification email: {e}")
                                # Don't fail registration if email fails
            else:
                features["password_strength"] = "unknown"
                features["password_score"] = 0

            # Save enrollment data using SQLAlchemy Feature/Enrollment models (preferred)
            try:
                # Resolve user_id
                uid = None
                if "user" in locals() and user:
                    uid = getattr(user, "id", None)
                else:
                    existing = auth_service.get_user_by_username(username)
                    if existing:
                        uid = getattr(existing, "id", None)

                if uid is not None:
                    # Expose resolved user id to fallback writers and for auditing
                    features["user_id"] = int(uid)
                    from app.models import EnrollmentVector
                    from app.models import db as sqlalchemy_db

                    ev = EnrollmentVector(username=username, user_id=uid, event_type="enrollment")

                    # --- Timestamp & duration ---
                    ev.timestamp     = datetime.now(timezone.utc).isoformat()
                    ev.total_duration = features.get("total_duration")

                    # --- Raw timing vectors ---
                    ev.H_vector  = json.dumps(features.get("H_vector",  []))
                    ev.DD_vector = json.dumps(features.get("DD_vector", []))
                    ev.UD_vector = json.dumps(features.get("UD_vector", []))
                    ev.UU_vector = json.dumps(features.get("UU_vector", []))
                    ev.DU_vector = json.dumps(features.get("DU_vector", []))

                    # --- Per-vector statistics ---
                    def _set_stats(ev_obj, prefix, stats_dict):
                        setattr(ev_obj, f"{prefix}_mean", stats_dict.get("mean"))
                        setattr(ev_obj, f"{prefix}_std",  stats_dict.get("std"))
                        setattr(ev_obj, f"{prefix}_min",  stats_dict.get("min"))
                        setattr(ev_obj, f"{prefix}_max",  stats_dict.get("max"))

                    _set_stats(ev, "H",  features.get("H_stats",  {}))
                    _set_stats(ev, "DD", features.get("DD_stats", {}))
                    _set_stats(ev, "UD", features.get("UD_stats", {}))
                    _set_stats(ev, "UU", features.get("UU_stats", {}))
                    _set_stats(ev, "DU", features.get("DU_stats", {}))

                    # --- Coefficient of variation (CV = std / mean) ---
                    def _cv(vec):
                        import statistics as _stat
                        if len(vec) < 2:
                            return None
                        m = _stat.mean(vec)
                        return _stat.stdev(vec) / m if m else None

                    ev.H_cv  = _cv(features.get("H_vector",  []))
                    ev.DD_cv = _cv(features.get("DD_vector", []))
                    ev.UD_cv = _cv(features.get("UD_vector", []))
                    ev.UU_cv = _cv(features.get("UU_vector", []))
                    ev.DU_cv = _cv(features.get("DU_vector", []))

                    # --- Typing speed (chars / second) ---
                    _dur = features.get("total_duration") or 0
                    _cnt = features.get("char_count", 0)
                    ev.typing_speed = (_cnt / _dur) if _dur > 0 else None

                    # --- Password hash ---
                    if password_hash:
                        ev.password_hash = password_hash

                    sqlalchemy_db.session.add(ev)
                    sqlalchemy_db.session.commit()
                else:
                    # Fallback to legacy DB manager if we couldn't resolve a user_id
                    saved_ok = db_manager.save_data(features)
                    if saved_ok is False:
                        print(f"[ERROR] register_sample: DB save failed for user {username}")
                        return (
                            jsonify(
                                {
                                    "status": "error",
                                    "message": "Database error saving sample",
                                }
                            ),
                            500,
                        )
                    new_count = biometric_service.get_enrollment_status(username)["count"]

            except Exception as e:
                print(f"[ERROR] register_sample save_data (sqlalchemy): {e}")
                traceback.print_exc()
                return (
                    jsonify({"status": "error", "message": "Database error saving sample"}),
                    500,
                )

            # Get updated enrollment count
            new_status = biometric_service.get_enrollment_status(username)
            new_count = new_status["count"]

            resp_payload = {
                "status": "success",
                "message": f"Sample {new_count}/20 saved successfully",
                "progress": {
                    "current": new_count,
                    "target": 20,
                    "complete": new_status["ready_for_login"],
                },
                "quality": quality,
                "password_strength": {
                    "strength": strength_result["strength"] if real_pass else "unknown",
                    "score": strength_result["score"] if real_pass else 0,
                    "label": (
                        get_strength_label(strength_result["score"]) if real_pass else "Unknown"
                    ),
                },
            }

            # Include password_event if we set a password on an existing account
            if "password_event" in locals() and password_event == "PASSWORD_SET_ON_EXISTING":
                resp_payload["password_event"] = password_event

            return jsonify(resp_payload)
        else:
            return jsonify({"status": "error", "message": result["msg"]}), 400

    except Exception as e:
        print(f"[ERROR] register_sample: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@api_bp.route("/pre_verify_password", methods=["POST"])
def pre_verify_password():
    """
    Pre-verify password before collection/verification mode
    """
    try:
        data = request.json
        username = data.get("username")
        raw_events = data.get("events")

        if not username or not raw_events:
            return jsonify({"valid": False, "message": "Data tidak lengkap"}), 400

        # Get enrollment data
        enrollment_data = db_manager.get_enrollment_samples(username)
        if not enrollment_data or len(enrollment_data) == 0:
            return jsonify({"valid": False, "message": "User not registered"}), 404

        # Process events
        result = process_web_events(raw_events, username)
        if result["status"] != "success":
            return (
                jsonify({"valid": False, "message": "Failed to process keystroke data"}),
                400,
            )

        features = result["features"]
        password_hash = result.get("password_hash", "")

        # Check security tier
        stored_hash = db_manager.get_password_hash(username)

        if stored_hash:
            # Modern security: Hash + Keystroke (STRICTER)
            print(f"[Pre-Verify] User '{username}' → Tier 2 (Hash + Keystroke)")

            if password_hash != stored_hash:
                return (
                    jsonify(
                        {
                            "valid": False,
                            "message": "Incorrect password",
                            "reason": "hash_mismatch",
                        }
                    ),
                    403,
                )

            keystroke_threshold = 0.2  # Stricter for modern users
            tier_label = "Hash+Keystroke"
        else:
            # Legacy: Keystroke only (LOOSER)
            print(f"[Pre-Verify] User '{username}' → Tier 1 (Keystroke Only)")
            keystroke_threshold = 0.4  # Looser for legacy users
            tier_label = "Keystroke Only (LEGACY)"

        verification_result = biometric_service.verify_keystroke_sample(
            username, features, use_statistical=False
        )
        if not verification_result.get("success"):
            return (
                jsonify(
                    {
                        "valid": False,
                        "message": verification_result.get("message", "Verification error"),
                        "reason": verification_result.get("reason", "verification_error"),
                    }
                ),
                400,
            )

        score = float(verification_result.get("score", 0.0))
        is_genuine = score >= keystroke_threshold

        print(
            f"[Pre-Verify] {tier_label} | Score: {score:.4f} | Result: {'PASS' if is_genuine else 'FAIL'}"
        )

        if not is_genuine:
            return (
                jsonify(
                    {
                        "valid": False,
                        "message": f"Ritme ketikan tidak cocok (score: {score:.3f})",
                        "reason": "keystroke_mismatch",
                        "score": score,
                        "threshold": keystroke_threshold,
                        "security_tier": "modern" if stored_hash else "legacy",
                    }
                ),
                403,
            )

        return (
            jsonify(
                {
                    "valid": True,
                    "message": "Pre-verification berhasil",
                    "score": score,
                    "threshold": keystroke_threshold,
                    "security_tier": "modern" if stored_hash else "legacy",
                }
            ),
            200,
        )

    except Exception as e:
        print(f"[ERROR] Pre-verification: {e}")
        traceback.print_exc()
        return jsonify({"valid": False, "message": f"Server Error: {str(e)}"}), 500


# ============================================================================
# LOGIN/VERIFICATION ENDPOINTS
# ============================================================================


def _fetch_enrollment_templates(username):
    """Fetch enrollment templates from SQLAlchemy (EnrollmentVector → KeystrokeVector fallback)."""

    def _parse_row(r):
        t = {}
        for key in ("H_vector", "DD_vector"):
            val = getattr(r, key, None)
            if val:
                try:
                    t[key] = json.loads(val)
                except Exception:
                    try:
                        t[key] = eval(val)
                    except Exception:
                        t[key] = []
            else:
                t[key] = []
        return t

    templates = []
    try:
        rows = db.session.execute(
            select(EnrollmentVector).where(EnrollmentVector.username == username)
        ).scalars().all()
        templates = [_parse_row(r) for r in rows]
    except Exception:
        templates = []

    if not templates:
        try:
            rows = db.session.execute(
                select(KeystrokeVector).where(
                    KeystrokeVector.username == username,
                    (KeystrokeVector.event_type == "enrollment")
                    | (KeystrokeVector.event_type == "enrollment_legacy"),
                )
            ).scalars().all()
            templates = [_parse_row(r) for r in rows]
        except Exception:
            templates = []

    return templates


@api_bp.route("/login", methods=["POST"])
@limiter.limit("10 per minute")  # Rate limit: 10 login attempts per minute
def login():
    """
    Unified login endpoint with comprehensive biometric verification
    """
    try:
        data = request.json
        identifier = (data.get("username", "") or "").strip()
        # Resolve identifier (username or email) to canonical username if possible
        user_obj = auth_service.get_user_by_identifier(identifier)
        if user_obj:
            username = user_obj.username
        else:
            username = identifier
        events = data.get("events")
        ip_address = request.remote_addr
        user_agent = request.headers.get("User-Agent", "Unknown")

        # Validate input
        if not username or not events:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Data tidak lengkap",
                        "reason": "invalid_input",
                    }
                ),
                400,
            )

        # Rate limiting (application-level)
        recent_failed = db_manager.get_failed_login_count_recent(username, minutes=15)
        # In development lenient mode we skip enforcing the lockout so developers can iterate
        from flask import current_app

        DEV_LENIENT = current_app.config.get("DEV_LENIENT_RATELIMIT", False)
        if recent_failed >= 5 and not DEV_LENIENT:
            db_manager.log_failed_login(username, "rate_limit_exceeded", ip_address, user_agent)
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Coba lagi nanti",
                        "reason": "rate_limit_exceeded",
                    }
                ),
                429,
            )
        if recent_failed >= 5 and DEV_LENIENT:
            # Log but continue for dev
            db_manager.log_failed_login(username, "rate_limit_skipped_dev", ip_address, user_agent)
            print(f"[DEV] Skipping rate-limit lockout for {username} in DEV_LENIENT mode")

        # Extract features
        result = process_web_events(events, username)
        if result["status"] == "error":
            db_manager.log_failed_login(username, "invalid_keystroke_data", ip_address, user_agent)
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Keystroke data tidak valid",
                        "reason": "invalid_data",
                    }
                ),
                400,
            )

        features = result["features"]

        # Pre-verify password/hash before biometric verification
        try:
            real_pass = result.get("real_password_string")
            password_hash = result.get("password_hash")
            user = auth_service.get_user_by_username(username)

            # Determine typed password char count from features
            typed_len = features.get("char_count", 0) or len(features.get("H_vector", []))

            # Fetch enrollment templates to find matching-length templates
            templates = []
            try:
                templates = (
                    biometric_service.db.get_enrollment_samples(username)
                    if biometric_service and getattr(biometric_service, "db", None)
                    else []
                )
            except Exception:
                try:
                    templates = db_manager.get_enrollment_samples(username)
                except Exception:
                    templates = []

            # Helper: check if any template has matching password length (H_vector length)
            def has_matching_length(templates_list, length):
                if not templates_list or length <= 0:
                    return False
                for t in templates_list:
                    hv = t.get("H_vector") or t.get("hold_times") or []
                    if isinstance(hv, (list, tuple)) and len(hv) == length:
                        return True
                return False

            matched_len = has_matching_length(templates, typed_len)

            # Only enforce password pre-check when typed length matches an enrollment template (defensive)
            if matched_len and user and getattr(user, "password_hash", None):
                if real_pass is None or not user.check_password(real_pass):
                    db_manager.log_failed_login(
                        username, "password_mismatch", ip_address, user_agent
                    )
                    return (
                        jsonify(
                            {
                                "success": False,
                                "message": "Incorrect password",
                                "reason": "PASSWORD_MISMATCH",
                            }
                        ),
                        403,
                    )

            elif matched_len:
                # Legacy/hash-based check (sha256 stored) - compare derived password_hash from client
                stored_hash = db_manager.get_password_hash(username)
                if stored_hash and password_hash and stored_hash != password_hash:
                    db_manager.log_failed_login(username, "hash_mismatch", ip_address, user_agent)
                    return (
                        jsonify(
                            {
                                "success": False,
                                "message": "Incorrect password",
                                "reason": "hash_mismatch",
                            }
                        ),
                        403,
                    )
        except Exception as e:
            print(f"[DEBUG] Pre-password-check error for {username}: {e}")

        # Check enrollment status via BiometricService
        enrollment_status = biometric_service.get_enrollment_status(username)
        enrollment_count = enrollment_status["count"]

        if enrollment_count == 0:
            db_manager.log_failed_login(username, "no_enrollment", ip_address, user_agent)
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "User not registered",
                        "reason": "no_enrollment",
                    }
                ),
                404,
            )

        # Attempt biometric verification even if not yet 'ready_for_login' so tests/mocked verification may pass
        # Prefer verifying with SQLAlchemy-sourced templates when user appears ready for login
        if enrollment_status.get("ready_for_login"):
            try:
                templates = _fetch_enrollment_templates(username)
                if templates:
                    try:
                        verification_result = biometric_service.verify_keystroke_sample(
                            result["features"], templates
                        )
                    except Exception:
                        verification_result = {"success": False, "verified": False, "score": 0.0}
                    if not verification_result.get("verified"):
                        try:
                            verification_result = biometric_service.verify_keystroke_sample(
                                username, result["features"]
                            )
                        except Exception:
                            verification_result = {"success": False, "verified": False, "score": 0.0}
                else:
                    verification_result = biometric_service.verify_keystroke_sample(
                        username, result["features"]
                    )
            except Exception:
                verification_result = biometric_service.verify_keystroke_sample(
                    username, result["features"]
                )
        else:
            verification_result = biometric_service.verify_keystroke_sample(
                username, result["features"]
            )
        if not verification_result.get("verified"):
            # Log the verification result for debugging
            try:
                from flask import current_app

                current_app.logger.debug(
                    f"[VERIFICATION FAILED] {username} -> {verification_result}"
                )
            except Exception:
                print(f"[VERIFICATION FAILED] {username} -> {verification_result}")

            # Try a secondary verification using SQLAlchemy-sourced templates if enrollment appears ready
            # This addresses cases where templates are stored in SQLAlchemy tables (EnrollmentVector / KeystrokeVector)
            try:
                if enrollment_status["ready_for_login"]:
                    templates = _fetch_enrollment_templates(username)
                    if templates:
                        secondary_ver = biometric_service.verify_keystroke_sample(
                            result["features"], templates
                        )
                        if secondary_ver.get("verified"):
                            verification_result = secondary_ver
                        else:
                            # As a last-resort fallback, run a lightweight local similarity check
                            try:
                                import numpy as _np

                                login_H = result["features"].get("H_vector", [])
                                # Build array of template H vectors that match length
                                template_Hs = [
                                    _np.array(t.get("H_vector", []), dtype=float)
                                    for t in templates
                                    if t.get("H_vector")
                                ]
                                if template_Hs and login_H:
                                    login_arr = _np.array(login_H, dtype=float)
                                    # truncate to minimum length
                                    min_len = min(
                                        login_arr.shape[0],
                                        *[a.shape[0] for a in template_Hs],
                                    )
                                    login_arr = login_arr[:min_len]
                                    aligned = [
                                        _np.array(a[:min_len], dtype=float) for a in template_Hs
                                    ]
                                    dists = [_np.linalg.norm(login_arr - a) for a in aligned]
                                    mean_dist = float(_np.mean(dists))
                                    fallback_score = 1.0 / (1.0 + mean_dist)
                                    if fallback_score >= 0.5:
                                        verification_result = {
                                            "success": True,
                                            "verified": True,
                                            "score": fallback_score,
                                            "confidence": "fallback",
                                        }
                            except Exception as _e:
                                print("[DEBUG] Fallback similarity check failed:", _e)
            except Exception as e:
                print(f"[DEBUG] Secondary verification attempt failed: {e}")

            # Development relaxation: if the confidence score is very close to threshold, allow in DEV
            DEV_LENIENT = current_app.config.get("DEV_LENIENT_RATELIMIT", False)
            relaxed_verified = False
            try:
                conf_score = float(
                    verification_result.get("score")
                    or verification_result.get("confidence_score")
                    or 0.0
                )
            except Exception:
                conf_score = 0.0

            if DEV_LENIENT and conf_score >= (biometric_service.MEDIUM_CONFIDENCE_THRESHOLD - 0.05):
                # Treat as verified in dev mode when score is within 0.05 of threshold
                relaxed_verified = True
                print(f"[DEV] Relaxed verification for {username}: score={conf_score}")

            if relaxed_verified:
                # Proceed as if verified (do not mark failed login)
                verification_result["relaxed_verification"] = True
                dev_relaxed_pass = True
            else:
                dev_relaxed_pass = False
                # If not enough enrollment, prefer returning insufficient_enrollment for guidance
                if not enrollment_status["ready_for_login"]:
                    db_manager.log_failed_login(
                        username, "insufficient_enrollment", ip_address, user_agent
                    )
                    payload = {
                        "success": False,
                        "message": f"Enrollment belum lengkap ({enrollment_count}/20)",
                        "reason": "insufficient_enrollment",
                    }
                    debug_requested = (request.json or {}).get("debug") or DEV_LENIENT
                    if debug_requested:
                        payload["debug"] = verification_result
                    return jsonify(payload), 400
                else:
                    db_manager.log_failed_login(
                        username, "verification_error", ip_address, user_agent
                    )
                    payload = {
                        "success": False,
                        "message": "Verification failed",
                        "reason": "verification_error",
                    }
                    debug_requested = (request.json or {}).get("debug") or DEV_LENIENT
                    if debug_requested:
                        payload["debug"] = verification_result
                    return jsonify(payload), 400
        # Get User model instance (use Session-based select to avoid legacy Query usage)
        from sqlalchemy import select

        user = db.session.execute(select(User).where(User.username == username)).scalars().first()
        if not user:
            db_manager.log_failed_login(username, "user_not_found", ip_address, user_agent)
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "User tidak ditemukan",
                        "reason": "user_not_found",
                    }
                ),
                404,
            )

        # Pre-verification: Password hash check via AuthService
        real_password = result.get("real_password_string")

        # Verify password (supports both bcrypt and legacy)
        password_verified = (
            auth_service.verify_password(user, real_password) if real_password else False
        )

        if not password_verified:
            db_manager.log_failed_login(
                username,
                "wrong_password_hash",
                ip_address,
                user_agent,
                verification_score=1.0,
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Incorrect password",
                        "reason": "wrong_password",
                    }
                ),
                403,
            )

        # If the user requires 2FA and password verification succeeded, prefer to proceed to 2FA
        # when enrollment is present (this keeps the login flow resilient and deterministic in tests)
        if user.two_factor_enabled and enrollment_status.get("ready_for_login"):
            session["2fa_user_id"] = user.id
            logout_user()
            return (
                jsonify(
                    {
                        "success": True,
                        "requires_2fa": True,
                        "message": "2FA verification required",
                        "redirect": "/auth/2fa/verify",
                    }
                ),
                200,
            )

        # Check if email verification is required (skip for admin)
        if not user.is_admin() and user.email and not user.email_verified:
            db_manager.log_failed_login(username, "email_not_verified", ip_address, user_agent)
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Email not verified. Check your inbox",
                        "reason": "email_not_verified",
                        "requires_verification": True,
                    }
                ),
                403,
            )

        # Comprehensive keystroke verification via BiometricService
        # Only re-run if not already confirmed by the earlier template-based SQLAlchemy check
        if not verification_result.get("verified"):
            verification_result = biometric_service.verify_keystroke_sample(username, features)
        # Ensure success key is present when already verified
        if verification_result.get("verified") and not verification_result.get("success"):
            verification_result["success"] = True

        # If dev relaxed pass was set earlier, override verification result to accept the login
        try:
            if "dev_relaxed_pass" in locals() and dev_relaxed_pass:
                verification_result = {
                    "success": True,
                    "verified": True,
                    "score": conf_score,
                    "confidence": verification_result.get("confidence", "low") + " (dev-relaxed)",
                }
        except Exception:
            pass

        if not verification_result.get("success"):
            db_manager.log_failed_login(username, "verification_error", ip_address, user_agent)
            return (
                jsonify(
                    {
                        "success": False,
                        "message": verification_result.get("message", "Verification error"),
                        "reason": "verification_error",
                    }
                ),
                500,
            )

        is_genuine = verification_result["verified"]
        confidence_score = verification_result.get("score", 0.0)

        # Decision logic
        if is_genuine:
            # Save verified login (audit log only — no raw biometric vectors)
            db_manager.save_verified_login(
                {
                    "username": username,
                    "password_hash": user.password_hash,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "verification_score": confidence_score,
                    "recommended_method": verification_result.get("confidence", "medium"),
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                }
            )

            # Use AuthService to create session (Flask-Login only)
            login_result = auth_service.login_user_session(user)
            if not login_result:
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "Failed to create session",
                            "reason": "session_error",
                        }
                    ),
                    500,
                )

            # Check if 2FA is enabled
            if user.two_factor_enabled:
                # Don't login yet, store user ID in session for 2FA verification
                session["2fa_user_id"] = user.id
                logout_user()  # Logout temporarily

                return (
                    jsonify(
                        {
                            "success": True,
                            "requires_2fa": True,
                            "message": "2FA verification required",
                            "redirect": "/auth/2fa/verify",
                        }
                    ),
                    200,
                )

            # Update last login
            user.last_login = datetime.now(timezone.utc)
            user.last_login_ip = ip_address
            db.session.commit()
            # Audit: successful login
            try:
                from app.models import AdminAudit

                a = AdminAudit(
                    user_id=getattr(user, "id", None),
                    username=getattr(user, "username", None),
                    action="login",
                    details=json.dumps({"ip": ip_address, "score": confidence_score}),
                )
                db.session.add(a)
                db.session.commit()
            except Exception:
                pass
            # Prepare response payload
            resp = {
                "success": True,
                "message": "Login successful",
                "score": confidence_score,
                "confidence_label": verification_result["confidence"],
                "templates_used": verification_result.get("templates_used", 0),
            }

            # No admin redirect here — admin should use /admin/login

            return jsonify(resp), 200

        else:
            # Log failed login
            db_manager.log_failed_login(
                username,
                "impostor_detected",
                ip_address,
                user_agent,
                verification_score=confidence_score,
            )

            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Login failed",
                        "reason": "impostor_detected",
                        "score": confidence_score,
                        "confidence_label": verification_result["confidence"],
                    }
                ),
                403,
            )

    except Exception as e:
        print(f"[ERROR] Login failed: {e}")
        traceback.print_exc()
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"Server Error: {str(e)}",
                    "reason": "server_error",
                }
            ),
            500,
        )


@api_bp.route("/verify_user", methods=["POST"])
def verify_user():
    """
    Verify user with comprehensive biometric analysis
    """
    try:
        data = request.json
        username = data.get("username")
        events = data.get("events")

        if not events or not username:
            return jsonify({"message": "Data tidak lengkap"}), 400

        # Process events
        process_result = process_web_events(events, username)
        if process_result["status"] == "error":
            return jsonify({"status": "error", "message": process_result["msg"]}), 400

        new_features = process_result["features"]

        # Get enrollment data
        enrollment_data = db_manager.get_enrollment_samples(username)

        if len(enrollment_data) < 5:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"User not registered or enrollment data insufficient ({len(enrollment_data)} samples)",
                    }
                ),
                404,
            )

        # Comprehensive verification
        verification_result = biometric_service.verify_keystroke_sample(username, new_features)
        if not verification_result.get("success"):
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": verification_result.get("message", "Verification error"),
                    }
                ),
                400,
            )

        # Log results
        new_features["username"] = username
        new_features["login_result"] = str(verification_result["verified"])
        new_features["login_score"] = verification_result["score"]
        new_features["event_type"] = "verification"
        db_manager.save_data(new_features)

        if verification_result["verified"]:
            return jsonify(
                {
                    "status": "success",
                    "message": "✅ Authentication successful!",
                    "result": True,
                    "score": verification_result["score"],
                    "comprehensive": verification_result,
                }
            )
        else:
            return jsonify(
                {
                    "status": "fail",
                    "message": "❌ Authentication failed",
                    "result": False,
                    "score": verification_result["score"],
                    "comprehensive": verification_result,
                }
            )

    except Exception as e:
        print(f"[ERROR] verify_user: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================================
# USER MANAGEMENT ENDPOINTS
# ============================================================================


@api_bp.route("/user/info", methods=["GET"])
@login_required  # Flask-Login protection
def get_user_info():
    """
    Get current user information
    Uses BiometricService to get enrollment status
    """
    print(
        f"[DEBUG] get_user_info called for user: {current_user.username if current_user.is_authenticated else 'Anonymous'}"
    )
    try:
        username = current_user.username  # Use Flask-Login current_user
        user_data = db_manager.get_user_by_username(username)
        from sqlalchemy import select

        user = db.session.execute(select(User).where(User.username == username)).scalars().first()

        if not user_data and not user:
            return jsonify({"error": "User not found"}), 404

        # Use BiometricService for enrollment status
        enrollment_status = biometric_service.get_enrollment_status(username)
        verified_logins = db_manager.get_verified_login_count(username)
        active_api_keys = APIKeyService.list_api_keys(
            user_id=current_user.id,
            active_only=True,
        )

        created_at = user.created_at.isoformat() if user and user.created_at else None
        email = user.email if user else user_data.get("email", "N/A")
        email_verified = bool(user.email_verified) if user else False
        has_password = bool(user.password_hash) if user else False

        return (
            jsonify(
                {
                    "username": username,
                    "email": email,
                    "email_verified": email_verified,
                    "created_at": created_at,
                    "last_login": user_data.get("last_login"),
                    "session_start": session.get("login_time"),
                    "enrollment_count": enrollment_status["count"],
                    "enrollment_ready": enrollment_status["ready_for_login"],
                    "verified_logins": verified_logins,
                    "has_password": has_password,
                    "api_key_count": len(active_api_keys),
                }
            ),
            200,
        )

    except Exception as e:
        print(f"[ERROR] get_user_info: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@api_bp.route("/user/api-keys", methods=["GET"])
@login_required
def list_user_api_keys():
    """List API keys created by the currently logged-in user."""
    try:
        include_inactive = request.args.get("include_inactive", "false").lower() == "true"
        api_keys = APIKeyService.list_api_keys(
            user_id=current_user.id,
            active_only=not include_inactive,
        )

        payload = []
        for key in api_keys:
            stats = APIKeyService.get_key_stats(key.id)
            payload.append(
                {
                    "id": key.id,
                    "partner_name": key.partner_name,
                    "description": key.description,
                    "key_prefix": key.key_prefix,
                    "is_active": bool(key.is_active),
                    "rate_limit": key.rate_limit,
                    "allowed_origins": key.allowed_origins,
                    "created_at": key.created_at.isoformat() if key.created_at else None,
                    "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
                    "expires_at": key.expires_at.isoformat() if key.expires_at else None,
                    "stats": stats,
                }
            )

        return jsonify({"success": True, "keys": payload, "count": len(payload)}), 200
    except Exception as e:
        print(f"[ERROR] list_user_api_keys: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


@api_bp.route("/user/api-keys/generate", methods=["POST"])
@login_required
@limiter.limit("5 per hour")
def generate_user_api_key():
    """Generate a new API key for partner integration from dashboard."""
    try:
        data = request.get_json(silent=True) or {}

        partner_name = (data.get("partner_name") or "").strip()
        description = (data.get("description") or "").strip() or None
        allowed_origins = (data.get("allowed_origins") or "").strip() or None

        if not partner_name:
            return jsonify({"success": False, "message": "partner_name is required"}), 400
        if len(partner_name) < 3:
            return (
                jsonify({"success": False, "message": "partner_name minimal 3 characters"}),
                400,
            )
        if len(partner_name) > 255:
            return (
                jsonify({"success": False, "message": "partner_name maximal 255 characters"}),
                400,
            )

        rate_limit_raw = data.get("rate_limit", 100)
        try:
            rate_limit = int(rate_limit_raw)
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "rate_limit must be a number"}), 400
        if rate_limit < 1 or rate_limit > 100000:
            return (
                jsonify({"success": False, "message": "rate_limit must be between 1 and 100000"}),
                400,
            )

        expires_days = data.get("expires_days")
        if expires_days in (None, ""):
            expires_days = None
        else:
            try:
                expires_days = int(expires_days)
            except (TypeError, ValueError):
                return jsonify({"success": False, "message": "expires_days must be a number"}), 400
            if expires_days < 1 or expires_days > 3650:
                return (
                    jsonify({"success": False, "message": "expires_days must be between 1 and 3650"}),
                    400,
                )

        full_key, key_model = APIKeyService.generate_new_key(
            user_id=current_user.id,
            partner_name=partner_name,
            description=description,
            rate_limit=rate_limit,
            allowed_origins=allowed_origins,
        )

        if expires_days is not None:
            key_model.expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)
            db.session.commit()

        return (
            jsonify(
                {
                    "success": True,
                    "message": "API key generated successfully",
                    "api_key": full_key,
                    "key": {
                        "id": key_model.id,
                        "partner_name": key_model.partner_name,
                        "description": key_model.description,
                        "key_prefix": key_model.key_prefix,
                        "rate_limit": key_model.rate_limit,
                        "is_active": bool(key_model.is_active),
                        "created_at": key_model.created_at.isoformat()
                        if key_model.created_at
                        else None,
                        "expires_at": key_model.expires_at.isoformat()
                        if key_model.expires_at
                        else None,
                    },
                    "warning": "Save this API key now. It will not be shown again.",
                }
            ),
            201,
        )
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] generate_user_api_key: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


@api_bp.route("/user/api-keys/<int:key_id>/deactivate", methods=["POST"])
@login_required
def deactivate_user_api_key(key_id):
    """Deactivate an API key owned by the current user."""
    try:
        ok = APIKeyService.deactivate_key(key_id, user_id=current_user.id)
        if not ok:
            return jsonify({"success": False, "message": "API key not found"}), 404

        return jsonify({"success": True, "message": "API key deactivated"}), 200
    except Exception as e:
        print(f"[ERROR] deactivate_user_api_key: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


@api_bp.route("/partner/enroll", methods=["POST"])
@limiter.limit("120 per minute")
def partner_enroll():
    """Enroll partner keystroke sample using API key authentication."""
    auth_context, auth_error = _authenticate_partner_api_request()
    if auth_error:
        return auth_error

    api_key = auth_context["api_key"]
    client_ip = auth_context["client_ip"]
    user_agent = auth_context["user_agent"]

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    raw_email = data.get("email")
    email = raw_email.strip() if isinstance(raw_email, str) else None

    if not username:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "username is required",
                    "error_code": "INVALID_INPUT",
                }
            ),
            400,
        )

    validation = auth_service.validate_username(username)
    if not validation["valid"]:
        return (
            jsonify(
                {
                    "success": False,
                    "message": validation["message"],
                    "error_code": "INVALID_USERNAME",
                }
            ),
            400,
        )

    log_entry = APIKeyService.log_enrollment(
        api_key_id=api_key.id,
        username=username,
        email=email,
        samples_count=1,
        client_ip=client_ip,
        user_agent=user_agent,
        status="processing",
    )

    try:
        features, typed_password, typed_password_hash, parse_error = _build_partner_features(
            data, username
        )
        if parse_error:
            log_entry.mark_failed(parse_error)
            return (
                jsonify(
                    {
                        "success": False,
                        "message": parse_error,
                        "error_code": "INVALID_KEYSTROKE_DATA",
                    }
                ),
                400,
            )

        quality = assess_sample_quality(features)
        features["username"] = username
        features["event_type"] = "enrollment"
        features["quality_label"] = quality["quality_label"]
        features["quality_score"] = quality["quality_score"]

        user = auth_service.get_user_by_username(username)
        created_new_user = False

        if user and email and not getattr(user, "email", None):
            user.email = email

        if user and typed_password and getattr(user, "password_hash", None):
            if not user.check_password(typed_password):
                log_entry.mark_failed("Incorrect password")
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "Incorrect password",
                            "error_code": "PASSWORD_MISMATCH",
                        }
                    ),
                    403,
                )

        if user and typed_password and not getattr(user, "password_hash", None):
            user.set_password(typed_password)

        if not user:
            create_password = typed_password or f"partner_{secrets.token_urlsafe(24)}"
            user_result = auth_service.create_user(username, create_password, email=email)
            if not user_result.get("success") or not user_result.get("user"):
                log_entry.mark_failed(user_result.get("message", "Unable to create user"))
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": user_result.get("message", "Unable to create user"),
                            "error_code": "USER_CREATION_FAILED",
                        }
                    ),
                    400,
                )

            user = user_result["user"]
            created_new_user = True

        from app.models import EnrollmentVector

        enrollment_row = EnrollmentVector(
            user_id=user.id,
            username=username,
            event_type="enrollment",
        )
        enrollment_row.H_vector = json.dumps(features.get("H_vector", []))
        enrollment_row.DD_vector = json.dumps(features.get("DD_vector", []))
        enrollment_row.UD_vector = json.dumps(features.get("UD_vector", []))
        enrollment_row.UU_vector = json.dumps(features.get("UU_vector", []))
        enrollment_row.DU_vector = json.dumps(features.get("DU_vector", []))
        enrollment_row.quality_label = quality["quality_label"]
        enrollment_row.quality_score = quality["quality_score"]
        if typed_password_hash:
            enrollment_row.password = typed_password_hash

        db.session.add(enrollment_row)
        db.session.commit()

        enrollment_status = biometric_service.get_enrollment_status(username)
        enrollment_id = f"enr_{api_key.id}_{log_entry.id}_{int(datetime.now(timezone.utc).timestamp())}"

        log_entry.user_id = user.id
        log_entry.samples_count = 1
        log_entry.mark_success(enrollment_id)

        api_key.total_enrollments = int(api_key.total_enrollments or 0) + 1
        if created_new_user:
            api_key.enrolled_users = int(api_key.enrolled_users or 0) + 1
        api_key.last_used_at = datetime.now(timezone.utc)
        db.session.commit()

        return (
            jsonify(
                {
                    "success": True,
                    "message": "Enrollment sample accepted",
                    "enrollment_id": enrollment_id,
                    "username": username,
                    "api_key_prefix": api_key.key_prefix,
                    "progress": {
                        "current": enrollment_status.get("count", 0),
                        "target": 20,
                        "complete": bool(enrollment_status.get("ready_for_login", False)),
                    },
                    "quality": quality,
                    "remaining_quota": api_key.get_remaining_quota(),
                }
            ),
            201,
        )

    except Exception as e:
        db.session.rollback()
        try:
            log_entry.mark_failed(str(e))
        except Exception:
            pass
        print(f"[ERROR] partner_enroll: {e}")
        traceback.print_exc()
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Failed to process enrollment request",
                    "error_code": "SERVER_ERROR",
                }
            ),
            500,
        )


@api_bp.route("/partner/verify", methods=["POST"])
@limiter.limit("180 per minute")
def partner_verify():
    """Verify partner keystroke sample using API key authentication."""
    auth_context, auth_error = _authenticate_partner_api_request()
    if auth_error:
        return auth_error

    api_key = auth_context["api_key"]
    client_ip = auth_context["client_ip"]
    user_agent = auth_context["user_agent"]

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()

    if not username:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "username is required",
                    "error_code": "INVALID_INPUT",
                }
            ),
            400,
        )

    validation = auth_service.validate_username(username)
    if not validation["valid"]:
        return (
            jsonify(
                {
                    "success": False,
                    "message": validation["message"],
                    "error_code": "INVALID_USERNAME",
                }
            ),
            400,
        )

    user = auth_service.get_user_by_username(username)
    user_id = user.id if user else None

    try:
        features, _, _, parse_error = _build_partner_features(data, username)
        if parse_error:
            APIKeyService.log_verification(
                api_key_id=api_key.id,
                user_id=user_id,
                username=username,
                verified=False,
                confidence_score=0.0,
                error_message=parse_error,
                client_ip=client_ip,
                user_agent=user_agent,
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "message": parse_error,
                        "error_code": "INVALID_KEYSTROKE_DATA",
                    }
                ),
                400,
            )

        templates = _load_partner_enrollment_templates(username)
        min_templates = int(
            getattr(biometric_service, "MIN_SAMPLES_FOR_VERIFICATION", 3) or 3
        )
        if len(templates) < min_templates:
            message = (
                f"Insufficient enrollment samples ({len(templates)}/{min_templates})"
            )
            APIKeyService.log_verification(
                api_key_id=api_key.id,
                user_id=user_id,
                username=username,
                verified=False,
                confidence_score=0.0,
                error_message=message,
                client_ip=client_ip,
                user_agent=user_agent,
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "message": message,
                        "error_code": "INSUFFICIENT_ENROLLMENT",
                    }
                ),
                404,
            )

        verification_result = biometric_service.verify_keystroke_sample(features, templates)

        verified = False
        confidence_score = None
        confidence_label = None
        decision = "impostor"

        if isinstance(verification_result, dict) and "decision" in verification_result:
            decision = verification_result.get("decision", "impostor")
            verified = decision == "genuine"
            confidence_score = verification_result.get("confidence_score")
            confidence_label = verification_result.get("confidence_label")
        else:
            verified = bool((verification_result or {}).get("verified", False))
            confidence_score = (verification_result or {}).get("score")
            confidence_label = (verification_result or {}).get("confidence")
            decision = "genuine" if verified else "impostor"

        verification_error = None
        if not verified:
            verification_error = (verification_result or {}).get(
                "error", "Biometric verification failed"
            )

        verification_log = APIKeyService.log_verification(
            api_key_id=api_key.id,
            user_id=user_id,
            username=username,
            verified=verified,
            confidence_score=confidence_score,
            error_message=verification_error,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        api_key.total_verifications = int(api_key.total_verifications or 0) + 1
        api_key.last_used_at = datetime.now(timezone.utc)
        db.session.commit()

        return (
            jsonify(
                {
                    "success": True,
                    "verified": bool(verified),
                    "decision": decision,
                    "username": username,
                    "confidence_score": confidence_score,
                    "confidence_label": confidence_label,
                    "templates_used": len(templates),
                    "verification_id": verification_log.id,
                    "api_key_prefix": api_key.key_prefix,
                    "remaining_quota": api_key.get_remaining_quota(),
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        try:
            APIKeyService.log_verification(
                api_key_id=api_key.id,
                user_id=user_id,
                username=username,
                verified=False,
                confidence_score=0.0,
                error_message=str(e),
                client_ip=client_ip,
                user_agent=user_agent,
            )
        except Exception:
            pass
        print(f"[ERROR] partner_verify: {e}")
        traceback.print_exc()
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Failed to process verification request",
                    "error_code": "SERVER_ERROR",
                }
            ),
            500,
        )


@api_bp.route("/user/reset_password", methods=["POST"])
@login_required  # Flask-Login protection
@limiter.limit("3 per hour")  # Rate limit: 3 password resets per hour
def reset_password():
    """
    Reset user password using AuthService
    """
    try:
        data = request.json
        new_password = data.get("new_password")
        username = current_user.username  # Use Flask-Login current_user

        if not new_password:
            return jsonify({"error": "New password required"}), 400

        current_password = data.get("current_password")

        if not current_password:
            return jsonify({"error": "Current password required to reset"}), 400

        success, message = auth_service.change_password(
            username, current_password, new_password
        )

        if not success:
            return jsonify({"error": message}), 400
        db_manager.delete_enrollment_data(username)

        # Logout user after password reset
        logout_user()
        session.clear()

        return (
            jsonify(
                {
                    "success": True,
                    "message": "Password reset successful. Please login again.",
                }
            ),
            200,
        )

    except Exception as e:
        print(f"[ERROR] reset_password: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ============================================================================
# DATASET COLLECTION API
# ============================================================================

@api_bp.route("/dataset/register", methods=["POST"])
def dataset_register():
    """Register a new dataset respondent and return their subject code.

    Request JSON (all fields optional):
        name_initial  str   Respondent's name or initials (optional, for researcher ref)

    Response JSON:
        subject_code  str   Auto-assigned code, e.g. "s001"
        session_no    int   Session to start from (always 1 for new subjects)
        repetition    int   Repetition to start from (always 1)
        total_sessions  int
        reps_per_session int
        target_phrase str
    """
    try:
        from app.models.dataset import (
            DATASET_REPS_PER_SESSION,
            DATASET_SESSIONS,
            DATASET_TARGET_PHRASE,
            DatasetSubject,
        )

        data = request.get_json(silent=True) or {}
        name_initial = (data.get("name_initial") or "").strip() or None

        # Auto-detect device info from User-Agent
        ua = request.headers.get("User-Agent", "")
        device_info = _parse_device_info(ua)

        subject_code = DatasetSubject.next_subject_code()
        subject = DatasetSubject(
            subject_code=subject_code,
            name_initial=name_initial,
            device_info=device_info,
        )
        db.session.add(subject)
        db.session.commit()

        return jsonify({
            "success": True,
            "subject_code": subject.subject_code,
            "subject_id": subject.id,
            "session_no": 1,
            "repetition": 1,
            "total_sessions": DATASET_SESSIONS,
            "reps_per_session": DATASET_REPS_PER_SESSION,
            "target_phrase": DATASET_TARGET_PHRASE,
        }), 201

    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] dataset_register: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/dataset/submit", methods=["POST"])
def dataset_submit():
    """Submit one keystroke sample for a registered respondent.

    Request JSON:
        subject_code  str   (required) Subject code, e.g. "s001"
        session_no    int   (required) 1-based session index
        repetition    int   (required) 1-based repetition within session
        raw_events    list  (required) Raw JS keystroke events from KeystrokeCapture

    Response JSON:
        success         bool
        repetition      int   Next repetition number
        session_no      int   Current (or next) session number
        session_done    bool  True when current session is complete
        all_done        bool  True when all sessions are complete
        progress        dict  {collected, total}
    """
    try:
        from app.models.dataset import (
            DATASET_REPS_PER_SESSION,
            DATASET_SESSIONS,
            DATASET_TARGET_PHRASE,
            DatasetEntry,
            DatasetSubject,
        )

        data = request.get_json(silent=True) or {}
        subject_code = data.get("subject_code", "").strip()
        session_no   = int(data.get("session_no", 1))
        repetition   = int(data.get("repetition", 1))
        raw_events   = data.get("raw_events", [])

        if not subject_code:
            return jsonify({"success": False, "error": "subject_code is required"}), 400
        if not raw_events:
            return jsonify({"success": False, "error": "raw_events is required"}), 400

        subject = DatasetSubject.query.filter_by(subject_code=subject_code).first()
        if subject is None:
            return jsonify({"success": False, "error": "Subject not found. Please register first."}), 404

        # Process keystroke events into feature vectors
        features = process_web_events(raw_events, username=f"dataset::{subject_code}")

        entry = DatasetEntry(
            subject_id=subject.id,
            session_no=session_no,
            repetition=repetition,
            target_phrase=DATASET_TARGET_PHRASE,
            total_duration=features.get("total_duration"),
            typing_speed=features.get("typing_speed"),
        )

        # Store raw vectors
        for vec_name in ("H", "DD", "UD", "UU", "DU"):
            vec = features.get(f"{vec_name}_vector", [])
            entry.set_vector(vec_name, vec)

        # Store per-vector statistics
        for vec_name in ("H", "DD", "UD", "UU", "DU"):
            for stat in ("mean", "std", "min", "max", "cv"):
                val = features.get(f"{vec_name}_{stat}")
                if val is not None:
                    setattr(entry, f"{vec_name}_{stat}", float(val))

        db.session.add(entry)
        db.session.commit()

        # Determine next state
        collected = subject.total_entries()
        total     = DATASET_SESSIONS * DATASET_REPS_PER_SESSION
        session_done = (repetition >= DATASET_REPS_PER_SESSION)
        all_done     = (collected >= total)

        next_session = session_no + 1 if session_done else session_no
        next_rep     = 1 if session_done else repetition + 1

        return jsonify({
            "success": True,
            "repetition": next_rep,
            "session_no": next_session,
            "session_done": session_done,
            "all_done": all_done,
            "progress": {
                "collected": collected,
                "total": total,
            },
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] dataset_submit: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/dataset/status/<subject_code>", methods=["GET"])
def dataset_status(subject_code):
    """Return current progress for a subject.

    Response JSON:
        subject_code       str
        total_entries      int
        completed_sessions int
        is_complete        bool
        current_session    int  Next session to work on
        current_rep        int  Next repetition within that session
        total_sessions     int
        reps_per_session   int
        target_phrase      str
    """
    try:
        from sqlalchemy import func

        from app.models.dataset import (
            DATASET_REPS_PER_SESSION,
            DATASET_SESSIONS,
            DATASET_TARGET_PHRASE,
            DatasetEntry,
            DatasetSubject,
        )

        subject = DatasetSubject.query.filter_by(subject_code=subject_code).first()
        if subject is None:
            return jsonify({"success": False, "error": "Subject not found"}), 404

        # Work out where the respondent left off
        last = (
            DatasetEntry.query
            .filter_by(subject_id=subject.id)
            .order_by(DatasetEntry.session_no.desc(), DatasetEntry.repetition.desc())
            .first()
        )

        if last is None:
            current_session = 1
            current_rep     = 1
        elif last.repetition >= DATASET_REPS_PER_SESSION:
            current_session = last.session_no + 1
            current_rep     = 1
        else:
            current_session = last.session_no
            current_rep     = last.repetition + 1

        return jsonify({
            "success": True,
            "subject_code": subject.subject_code,
            "total_entries": subject.total_entries(),
            "completed_sessions": subject.completed_sessions(),
            "is_complete": subject.is_complete(),
            "current_session": current_session,
            "current_rep": current_rep,
            "total_sessions": DATASET_SESSIONS,
            "reps_per_session": DATASET_REPS_PER_SESSION,
            "target_phrase": DATASET_TARGET_PHRASE,
        }), 200

    except Exception as e:
        print(f"[ERROR] dataset_status: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


def _parse_device_info(user_agent: str) -> str:
    """Extract a concise device/browser label from a User-Agent string."""
    ua = user_agent.lower()

    # OS detection
    if "android" in ua:
        os_label = "Android"
    elif "iphone" in ua or "ipad" in ua:
        os_label = "iOS"
    elif "windows" in ua:
        os_label = "Windows"
    elif "mac os" in ua or "macintosh" in ua:
        os_label = "macOS"
    elif "linux" in ua:
        os_label = "Linux"
    else:
        os_label = "Unknown OS"

    # Browser detection
    if "edg/" in ua or "edge/" in ua:
        browser = "Edge"
    elif "opr/" in ua or "opera" in ua:
        browser = "Opera"
    elif "chrome/" in ua and "chromium" not in ua:
        browser = "Chrome"
    elif "firefox/" in ua:
        browser = "Firefox"
    elif "safari/" in ua and "chrome" not in ua:
        browser = "Safari"
    else:
        browser = "Other"

    return f"{browser}/{os_label}"


