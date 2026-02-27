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

from app import limiter as _limiter

from ._shared import api_bp, auth_service, biometric_service, db_manager


@api_bp.route("/user/info", methods=["GET"])
@login_required
def get_user_info():
    """Get current user information and enrollment status."""
    print(
        f"[DEBUG] get_user_info called for user: "
        f"{current_user.username if current_user.is_authenticated else 'Anonymous'}"
    )
    try:
        username = current_user.username

        # current_user IS the SQLAlchemy User model object; use it directly.
        # Fall back to db_manager only for legacy-only deployments where ORM
        # columns may be absent.
        email = getattr(current_user, "email", None) or "N/A"
        last_login = getattr(current_user, "last_login", None)

        enrollment_status = biometric_service.get_enrollment_status(username)
        verified_logins = db_manager.get_verified_login_count(username)

        return jsonify({
            "username": username,
            "email": email,
            "last_login": last_login,
            "session_start": session.get("login_time"),
            "enrollment_count": enrollment_status["count"],
            "enrollment_ready": enrollment_status["ready_for_login"],
            "verified_logins": verified_logins,
        }), 200

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
        data = request.json
        new_password = data.get("new_password")
        username = current_user.username

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

        logout_user()
        session.clear()

        return jsonify({
            "success": True,
            "message": "Password reset successful. Please login again.",
        }), 200

    except Exception as e:
        print(f"[ERROR] reset_password: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
