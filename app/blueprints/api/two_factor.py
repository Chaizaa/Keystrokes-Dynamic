"""
Two-Factor Authentication (2FA) endpoints.

Routes
------
POST /api/2fa/enroll
POST /api/2fa/confirm
POST /api/2fa/verify
"""

import traceback

from datetime import datetime, timezone

from flask import jsonify, request, session
from sqlalchemy import select

from app.models import User, db

from ._shared import api_bp, get_auth_service


def _fetch_user(username: str):
    return db.session.execute(select(User).where(User.username == username)).scalars().first()


@api_bp.route("/2fa/enroll", methods=["POST"])
def enroll_2fa():
    """Create a TOTP secret for the user and return it for provisioning."""
    try:
        data = request.json or {}
        username = data.get("username")
        if not username:
            return jsonify({"success": False, "message": "Data tidak lengkap"}), 400

        user = _fetch_user(username)
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
    """Confirm a TOTP token and enable 2FA for the user."""
    try:
        data = request.json or {}
        username = data.get("username")
        token = data.get("token")
        if not username or not token:
            return jsonify({"success": False, "message": "Data tidak lengkap"}), 400

        if not get_auth_service().verify_two_factor_token(username, token):
            return jsonify({"success": False, "message": "Token tidak valid"}), 400

        user = _fetch_user(username)
        user.two_factor_enabled = True
        db.session.commit()
        return jsonify({"success": True, "message": "2FA diaktifkan"}), 200

    except Exception as e:
        print(f"[ERROR] confirm_2fa: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


@api_bp.route("/2fa/verify", methods=["POST"])
def verify_2fa():
    """Verify a TOTP token for a user (called after login to complete 2FA step)."""
    try:
        data = request.json or {}
        username = (data.get("username") or session.get("2fa_username") or "").strip()
        token = data.get("token")
        if not username or not token:
            return jsonify({"success": False, "message": "Data tidak lengkap"}), 400

        pending_user_id = session.get("2fa_user_id")
        user = _fetch_user(username)
        if not user:
            return jsonify({"success": False, "message": "User tidak ditemukan"}), 404
        if pending_user_id and int(pending_user_id) != int(user.id):
            return jsonify({"success": False, "message": "Session 2FA tidak valid"}), 403

        ok = get_auth_service().verify_two_factor_token(username, token)
        if not ok:
            return jsonify({"success": False, "message": "Token tidak valid"}), 400

        if not get_auth_service().login_user_session(user):
            return jsonify({"success": False, "message": "Session creation failed"}), 500

        user.last_login = datetime.now(timezone.utc)
        db.session.commit()

        session.pop("2fa_user_id", None)
        session.pop("2fa_username", None)
        return jsonify({"success": True, "redirect": "/dashboard"}), 200

    except Exception as e:
        print(f"[ERROR] verify_2fa: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500
