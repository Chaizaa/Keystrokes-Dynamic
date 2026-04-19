"""
User management endpoints (requires authentication).

Routes
------
GET  /api/user/info
POST /api/user/reset_password
"""

import traceback

from flask import jsonify, request, session
from flask_login import current_user, login_required, logout_user
from sqlalchemy import delete, func, select

from app import limiter as _limiter
from app.models import LoginAttempt, UsersVector, db

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


def _build_user_info_payload(username: str) -> dict:
    """Build stable response payload for /api/user/info endpoint."""
    email = getattr(current_user, "email", None) or "N/A"
    last_login = getattr(current_user, "last_login", None)
    enrollment_status = get_biometric_service().get_enrollment_status(username)

    return {
        "username": username,
        "email": email,
        "last_login": last_login,
        "session_start": session.get("login_time"),
        "enrollment_count": enrollment_status["count"],
        "enrollment_ready": enrollment_status["ready_for_login"],
        "verified_logins": _count_verified_logins(username),
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
