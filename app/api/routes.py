from flask import Blueprint, request, jsonify, current_app, g

from app.api import require_api_auth

from app.services.biometric_engine import enroll_user, verify_user
from app.services.biometric import BiometricService

api_bp = Blueprint("api_v1", __name__)


def _bad_request(message):
    return jsonify({"error": message}), 400


@api_bp.route("/enroll", methods=["POST"])
@require_api_auth
def enroll():
    if not request.is_json:
        return _bad_request("Request must be application/json")

    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    keystroke_data = data.get("keystroke_data")

    if not user_id:
        return _bad_request("Missing user_id")
    if keystroke_data is None:
        return _bad_request("Missing keystroke_data")
    if not isinstance(keystroke_data, list):
        return _bad_request("keystroke_data must be a list")

    try:
        # Identify user via API credential attached by decorator
        cred = getattr(g, "api_credential", None)
        if not cred:
            return jsonify({"error": "unauthorized"}), 401
        user = getattr(cred, "user", None)
        if not user:
            return jsonify({"error": "user not found for credential"}), 401

        # Enforce minimum samples: at least 10 (or configured value, but never below 10)
        configured_min = int(current_app.config.get("MIN_ENROLLMENT_SAMPLES", 10) or 10)
        min_required = max(10, configured_min)

        # Persist samples
        processed = enroll_user(user.id, keystroke_data)

        # Use BiometricService to get updated status
        bio = BiometricService()
        status = bio.get_enrollment_status(user.username)
        collected = int(status.get("count", 0))

        if collected >= min_required:
            return (
                jsonify({"status": "completed", "samples_collected": collected}),
                200,
            )
        else:
            remaining = int(max(0, min_required - collected))
            return (
                jsonify({"status": "collecting", "samples_collected": collected, "remaining": remaining}),
                200,
            )
    except Exception as e:
        current_app.logger.error("Enroll error: %s", e, exc_info=True)
        return jsonify({"error": "internal server error"}), 500


@api_bp.route("/verify", methods=["POST"])
@require_api_auth
def verify():
    if not request.is_json:
        return _bad_request("Request must be application/json")

    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    keystroke_data = data.get("keystroke_data")

    if not user_id:
        return _bad_request("Missing user_id")
    if keystroke_data is None:
        return _bad_request("Missing keystroke_data")
    if not (isinstance(keystroke_data, list) or isinstance(keystroke_data, dict)):
        return _bad_request("keystroke_data must be a list or object")

    try:
        cred = getattr(g, "api_credential", None)
        if not cred:
            return jsonify({"error": "unauthorized"}), 401
        user = getattr(cred, "user", None)
        if not user:
            return jsonify({"error": "user not found for credential"}), 401

        verified, score = verify_user(user.id, keystroke_data)
        threshold = float(current_app.config.get("VERIFICATION_THRESHOLD", 0.7))
        return (
            jsonify({"verified": bool(verified), "score": float(score), "threshold": threshold}),
            200,
        )
    except Exception as e:
        current_app.logger.error("Verify error: %s", e, exc_info=True)
        return jsonify({"error": "internal server error"}), 500
