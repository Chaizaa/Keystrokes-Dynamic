"""
Two-Factor Authentication (2FA) endpoints.

Routes
------
POST /api/2fa/enroll
POST /api/2fa/confirm
POST /api/2fa/verify
"""

import traceback

from flask import jsonify, request
from sqlalchemy import select

from app.models import User, db
from app.services import AuthService

from ._shared import api_bp


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

        auth = AuthService()
        if not auth.verify_two_factor_token(username, token):
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
        username = data.get("username")
        token = data.get("token")
        if not username or not token:
            return jsonify({"success": False, "message": "Data tidak lengkap"}), 400

        auth = AuthService()
        ok = auth.verify_two_factor_token(username, token)
        return jsonify({"success": ok}), (200 if ok else 400)

    except Exception as e:
        print(f"[ERROR] verify_2fa: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500
