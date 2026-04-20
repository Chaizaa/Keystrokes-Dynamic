"""
User management endpoints (requires authentication).

Routes
------
GET  /api/user/info
POST /api/user/reset_password
"""

import traceback
from datetime import datetime, timedelta, timezone

from flask import jsonify, request, session
from flask_login import current_user, login_required, logout_user
from sqlalchemy import delete, func, select

from app import limiter as _limiter
from app.models import APIKey, LoginAttempt, UsersVector, db
from app.services.api_key_service import APIKeyService

# Keep legacy module-level symbols for compatibility with existing imports/tests.
from ._shared import (
    api_bp,
    auth_service,
    biometric_service,
    get_auth_service,
    get_biometric_service,
)


def _get_current_username() -> str:
    """Return authenticated username from current session context."""
    return current_user.username


def _count_verified_logins(username: str) -> int:
    """Count successful login attempts for user from ORM log table."""
    return int(
        db.session.execute(
            select(func.count())
            .select_from(LoginAttempt)
            .where(LoginAttempt.username == username, LoginAttempt.success == True)  # noqa: E712
        ).scalar()
        or 0
    )


def _count_active_api_keys(user_id: int) -> int:
    """Count active API keys owned by a user."""
    try:
        return int(
            db.session.execute(
                select(func.count())
                .select_from(APIKey)
                .where(APIKey.user_id == user_id, APIKey.is_active == True)  # noqa: E712
            ).scalar()
            or 0
        )
    except Exception:
        return 0


def _iso(dt_value):
    """Safely serialize datetime value to ISO string."""
    if dt_value is None:
        return None
    try:
        return dt_value.isoformat()
    except Exception:
        return str(dt_value)


def _serialize_api_key(api_key: APIKey) -> dict:
    """Serialize API key model for dashboard JSON payload."""
    stats = APIKeyService.get_key_stats(api_key.id)
    return {
        "id": api_key.id,
        "partner_name": api_key.partner_name,
        "key_prefix": api_key.key_prefix,
        "description": api_key.description,
        "is_active": bool(api_key.is_active),
        "rate_limit": api_key.rate_limit,
        "allowed_origins": api_key.allowed_origins,
        "created_at": _iso(api_key.created_at),
        "last_used_at": _iso(api_key.last_used_at),
        "expires_at": _iso(api_key.expires_at),
        "stats": {
            "total_enrollments": int(stats.get("total_enrollments", 0)),
            "total_verifications": int(stats.get("total_verifications", 0)),
            "successful_enrollments": int(stats.get("successful_enrollments", 0)),
            "successful_verifications": int(stats.get("successful_verifications", 0)),
        },
    }


def _build_user_info_payload(username: str) -> dict:
    """Build stable response payload for /api/user/info endpoint."""
    email = getattr(current_user, "email", None) or "N/A"
    last_login = getattr(current_user, "last_login", None)
    enrollment_status = get_biometric_service().get_enrollment_status(username)

    return {
        "username": username,
        "email": email,
        "email_verified": bool(getattr(current_user, "email_verified", False)),
        "created_at": _iso(getattr(current_user, "created_at", None)),
        "last_login": last_login,
        "session_start": session.get("login_time"),
        "enrollment_count": enrollment_status["count"],
        "enrollment_ready": enrollment_status["ready_for_login"],
        "verified_logins": _count_verified_logins(username),
        "has_password": bool(getattr(current_user, "password_hash", None)),
        "api_key_count": _count_active_api_keys(current_user.id),
    }


def _validate_reset_password_payload(data: dict):
    """Validate reset password payload and return normalized credentials."""
    new_password = data.get("new_password")
    if not new_password:
        return None, None, (jsonify({"error": "New password required"}), 400)

    current_password = data.get("current_password")
    if not current_password:
        return None, None, (jsonify({"error": "Current password required to reset"}), 400)

    return new_password, current_password, None


def _clear_enrollment_vectors(username: str) -> None:
    """Delete enrollment vectors after successful password reset."""
    db.session.execute(
        delete(UsersVector).where(
            UsersVector.username == username,
            (UsersVector.event_type == "enrollment")
            | (UsersVector.data_type == "enrollment"),
        )
    )


@api_bp.route("/user/info", methods=["GET"])
@login_required
def get_user_info():
    """Get current user information and enrollment status."""
    print(
        f"[DEBUG] get_user_info called for user: "
        f"{current_user.username if current_user.is_authenticated else 'Anonymous'}"
    )
    try:
        username = _get_current_username()
        return jsonify(_build_user_info_payload(username)), 200

    except Exception as e:
        print(f"[ERROR] get_user_info: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@api_bp.route("/user/reset_password", methods=["POST"])
@login_required
@_limiter.limit("3 per hour")
def reset_password():
    """Reset the current user's password. Clears enrollment data and logs out."""
    try:
        data = request.json or {}
        username = _get_current_username()

        new_password, current_password, validation_error = _validate_reset_password_payload(data)
        if validation_error:
            return validation_error

        success, message = get_auth_service().change_password(
            username, current_password, new_password
        )
        if not success:
            return jsonify({"error": message}), 400

        _clear_enrollment_vectors(username)
        db.session.commit()

        logout_user()
        session.clear()

        return jsonify({
            "success": True,
            "message": "Password reset successful. Please login again.",
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] reset_password: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@api_bp.route("/user/api-keys", methods=["GET"])
@login_required
def list_user_api_keys():
    """List API keys owned by the currently authenticated user."""
    try:
        include_inactive = str(
            request.args.get("include_inactive", "false")
        ).strip().lower() in {"1", "true", "yes"}

        keys = APIKeyService.list_api_keys(
            user_id=current_user.id,
            active_only=not include_inactive,
        )

        return jsonify({
            "success": True,
            "keys": [_serialize_api_key(k) for k in keys],
        }), 200

    except Exception as e:
        print(f"[ERROR] list_user_api_keys: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": "Failed to list API keys"}), 500


@api_bp.route("/user/api-keys/generate", methods=["POST"])
@login_required
@_limiter.limit("10 per hour")
def generate_user_api_key():
    """Generate a new API key for dashboard-managed partner integration."""
    try:
        data = request.json or {}

        partner_name = (data.get("partner_name") or "").strip()
        if not partner_name:
            return jsonify({"success": False, "message": "partner_name is required"}), 400

        description = (data.get("description") or "").strip() or None
        allowed_origins = (data.get("allowed_origins") or "").strip() or None

        try:
            rate_limit = int(data.get("rate_limit", 100))
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "rate_limit must be a number"}), 400

        if rate_limit <= 0 or rate_limit > 100000:
            return jsonify({"success": False, "message": "rate_limit must be between 1 and 100000"}), 400

        expires_days_raw = data.get("expires_days")
        expires_days = None
        if expires_days_raw not in (None, ""):
            try:
                expires_days = int(expires_days_raw)
            except (TypeError, ValueError):
                return jsonify({"success": False, "message": "expires_days must be a number"}), 400
            if expires_days <= 0 or expires_days > 3650:
                return jsonify({"success": False, "message": "expires_days must be between 1 and 3650"}), 400

        full_key, api_key = APIKeyService.generate_new_key(
            user_id=current_user.id,
            partner_name=partner_name,
            description=description,
            rate_limit=rate_limit,
            allowed_origins=allowed_origins,
        )

        if expires_days is not None:
            api_key.expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)
            db.session.commit()

        return jsonify({
            "success": True,
            "message": "API key generated",
            "warning": "Store this key now. It will not be shown again.",
            "api_key": full_key,
            "key": _serialize_api_key(api_key),
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] generate_user_api_key: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": "Failed to generate API key"}), 500


@api_bp.route("/user/api-keys/<int:api_key_id>/deactivate", methods=["POST"])
@login_required
@_limiter.limit("30 per hour")
def deactivate_user_api_key(api_key_id: int):
    """Deactivate one API key that belongs to the authenticated user."""
    try:
        success = APIKeyService.deactivate_key(api_key_id, user_id=current_user.id)
        if not success:
            return jsonify({"success": False, "message": "API key not found"}), 404

        return jsonify({"success": True, "message": "API key deactivated"}), 200

    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] deactivate_user_api_key: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": "Failed to deactivate API key"}), 500
