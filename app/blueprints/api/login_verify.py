"""
Additional login verification endpoints.

Routes
------
POST /api/pre_verify_password
POST /api/verify_user
"""

import json
import traceback
from datetime import datetime, timezone

from flask import jsonify, request
from sqlalchemy import select

from app.models import User, UsersVector, db

from ._shared import (
    api_bp,
    get_auth_service,
    get_biometric_service,
)
from .helpers import process_events, save_biometric_sample



@api_bp.route("/pre_verify_password", methods=["POST"])
def pre_verify_password():
    """Pre-verify password before collection / verification mode."""
    try:
        data = request.json
        username = data.get("username")
        raw_events = data.get("events")

        if not username or not raw_events:
            return jsonify({"valid": False, "message": "Data tidak lengkap"}), 400

        enrollment_status = get_biometric_service().get_enrollment_status(username)
        enrollment_count = int(enrollment_status.get("count", 0))
        if enrollment_count == 0:
            return jsonify({"valid": False, "message": "User not registered"}), 404

        # Same enrollment-adequacy gate as /api/login: never report a match for
        # an account that has not completed the required enrollment samples. A
        # model trained on too few samples can be degenerate and falsely verify.
        if not enrollment_status.get("ready_for_login"):
            return jsonify({
                "valid": False,
                "message": (
                    f"Enrollment incomplete "
                    f"({enrollment_count}/{enrollment_status.get('recommended_samples')})"
                ),
                "reason": "insufficient_enrollment",
            }), 403

        result = process_events(raw_events, username)
        if result["status"] != "success":
            return jsonify({"valid": False,
                            "message": "Failed to process keystroke data"}), 400

        features = result["features"]
        real_pass = result.get("real_password_string")
        user_obj = get_auth_service().get_user_by_identifier(username)

        if user_obj and getattr(user_obj, "password_hash", None):
            print(f"[Pre-Verify] User '{username}' → Password check enabled")
            if real_pass is None or not user_obj.check_password(real_pass):
                return jsonify({"valid": False,
                                "message": "Incorrect password",
                                "reason": "password_mismatch"}), 403

        verification_result = get_biometric_service().verify_keystroke_sample(username, features)
        if not verification_result.get("success"):
            return jsonify({"valid": False,
                            "message": verification_result.get("message", "Verification error"),
                            "reason": verification_result.get("reason", "verification_error")}), 400

        score = float(verification_result.get("score", 0.0))
        if not verification_result.get("verified"):
            return jsonify({
                "valid": False,
                "message": f"Ritme ketikan tidak cocok (score: {score:.3f})",
                "reason": "keystroke_mismatch",
                "score": score,
                "threshold": verification_result.get("threshold"),
            }), 403

        return jsonify({
            "valid": True,
            "message": "Pre-verification berhasil",
            "score": score,
            "threshold": verification_result.get("threshold"),
        }), 200

    except Exception as e:
        print(f"[ERROR] Pre-verification: {e}")
        traceback.print_exc()
        return jsonify({"valid": False, "message": f"Server Error: {str(e)}"}), 500


@api_bp.route("/verify_user", methods=["POST"])
def verify_user():
    """Verify user with comprehensive biometric analysis."""
    try:
        data = request.json
        username = data.get("username")
        events = data.get("events")

        if not events or not username:
            return jsonify({"message": "Data tidak lengkap"}), 400

        process_result = process_events(events, username)
        if process_result["status"] == "error":
            return jsonify({"status": "error",
                            "message": process_result["msg"]}), 400

        new_features = process_result["features"]
        enrollment_status = get_biometric_service().get_enrollment_status(username)
        enrollment_count = int(enrollment_status.get("count", 0))
        # Enrollment-adequacy gate (see /api/login): require the full enrollment
        # sample count before a verification result can be trusted. The old
        # hard-coded `< 5` let an under-enrolled account be "authenticated" by a
        # model trained on too few samples.
        if not enrollment_status.get("ready_for_login"):
            return jsonify({
                "status": "error",
                "message": (f"User not registered or enrollment data insufficient "
                            f"({enrollment_count}/{enrollment_status.get('recommended_samples')} samples)"),
            }), 404

        verification_result = get_biometric_service().verify_keystroke_sample(username, new_features)
        if not verification_result.get("success"):
            return jsonify({"status": "error",
                            "message": verification_result.get("message",
                                                               "Verification error")}), 400

        # Save verification record via centralized helper
        user_obj = get_auth_service().get_user_by_username(username)
        save_biometric_sample(
            username,
            getattr(user_obj, "id", None),
            new_features,
            event_type="login",
            data_type="verification",
            is_successful=verification_result.get("verified"),
        )
        db.session.commit()

        if verification_result["verified"]:
            return jsonify({
                "status": "success", "message": "✅ Authentication successful!",
                "result": True, "score": verification_result["score"],
                "comprehensive": verification_result,
            })
        else:
            return jsonify({
                "status": "fail", "message": "❌ Authentication failed",
                "result": False, "score": verification_result["score"],
                "comprehensive": verification_result,
            })

    except Exception as e:
        print(f"[ERROR] verify_user: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500
