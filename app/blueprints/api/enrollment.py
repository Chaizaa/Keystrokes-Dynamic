"""
Enrollment (registration) endpoints.

Routes
------
POST /api/check_username
POST /api/register_sample
"""

import traceback

from flask import jsonify, request

from app import limiter as _limiter
from app.models import db
from app.utils.password_strength import calculate_password_strength, get_strength_label

# Keep legacy module-level symbols for compatibility with existing imports/tests.
from ._shared import (
    api_bp,
    auth_service,
    biometric_service,
    get_auth_service,
    get_biometric_service,
)
from .helpers import assess_quality, error_response, process_events, save_biometric_sample


# Local stats helper removed in favor of consolidated save_biometric_sample in .helpers


# Removed local wrappers in favor of .helpers imports


def _recommended_samples():
    """Return the enrollment target from the biometric service or its legacy fallback."""
    getter = getattr(get_biometric_service(), "get_recommended_samples", None)
    if callable(getter):
        try:
            return int(getter())  # type: ignore
        except Exception:
            pass
    return int(getattr(get_biometric_service(), "RECOMMENDED_SAMPLES", 30))


def _resolve_username_for_check(username):
    """Resolve email identifier to username for check_username endpoint."""
    try:
        if "@" in username:
            user_obj = get_auth_service().get_user_by_email(username)
            if user_obj:
                return user_obj.username, None
            return username, (
                jsonify({
                    "exists": False,
                    "can_login": False,
                    "enrollment_complete": False,
                    "enrollment_count": 0,
                    "message": f"User {username} tidak ditemukan",
                }),
                200,
            )
    except Exception:
        pass

    return username, None


def _build_check_username_login_response(username, availability, enrollment_count, login_ready):
    """Build check_username response payload for login mode."""
    recommended = _recommended_samples()
    if not availability["exists"]:
        return jsonify({
            "exists": False,
            "can_login": False,
            "enrollment_complete": False,
            "enrollment_count": 0,
            "message": f"User {username} tidak ditemukan",
        }), 200

    return jsonify({
        "exists": True,
        "can_login": login_ready,
        "enrollment_complete": login_ready,
        "enrollment_count": enrollment_count,
        "message": (
            f"User {username} ditemukan"
            if login_ready
            else (
                f"Enrollment belum lengkap "
                f"({enrollment_count}/{recommended})"
            )
        ),
    }), 200


def _build_check_username_register_response(availability, enrollment_count):
    """Build check_username response payload for register mode.

    A username is only "resumable" when there is unfinished enrollment for an
    account that hasn't completed registration (no password set yet, or partial
    enrollment). A fully-registered user (password_hash present) must always be
    reported as "taken" — otherwise the UI lets an attacker proceed against an
    existing account.
    """
    recommended = _recommended_samples()

    fully_registered = False
    if availability.get("exists"):
        _data = request.json or {}
        existing_user = get_auth_service().get_user_by_username(
            (_data.get("username") or "").strip()
        )
        fully_registered = bool(
            existing_user and getattr(existing_user, "password_hash", None)
        )

    if fully_registered:
        status_str = "taken"
    elif availability.get("exists") or (
        not availability["available"] and availability.get("reason") == "resumable"
    ):
        status_str = "resumable"
    elif not availability["available"]:
        status_str = "taken"
    else:
        status_str = "available"

    response_data = {
        "status": status_str,
        "available": availability["available"] and not fully_registered,
        "exists": availability["exists"],
        "message": (
            "Username sudah terdaftar" if fully_registered else availability["message"]
        ),
        "enrollment_count": enrollment_count,
        "is_retry": enrollment_count > 0,
        "detail": "",
    }

    if status_str == "resumable" and availability.get("exists"):
        response_data["message"] = (
            f"Resume registration: {enrollment_count}/{recommended} samples collected"
        )

    return jsonify(response_data)


def _extract_register_payload(data):
    """Extract username/events/email payload from register_sample request JSON."""
    username = (data.get("username") or "").strip()
    events = data.get("events")
    raw_email = data.get("email", None)
    email = raw_email.strip() or None if isinstance(raw_email, str) else None
    return username, events, email


def _validate_register_payload(username, events):
    """Validate required fields and username format for register_sample."""
    if not events or not username:
        return error_response("Data tidak lengkap", status_code=400)

    validation = get_auth_service().validate_username(username)
    if not validation["valid"]:
        return error_response(validation["message"], status_code=400)

    return None


def _prepare_enrollment_features(username, events):
    """Process raw events and enrich features with quality metadata."""
    result = process_events(events, username)
    if result["status"] != "success":
        return None, None, None, error_response(result["msg"], status_code=400), 400

    features = result["features"]
    features["username"] = username
    features["event_type"] = "enrollment"

    quality = assess_quality(features)
    features["quality_label"] = quality["quality_label"]
    features["quality_score"] = quality["quality_score"]

    return result, features, quality, None, None


def _set_password_on_existing_user(existing_user, real_pass, username):
    """Set password for existing user that previously had no password."""
    try:
        existing_user.set_password(real_pass)
        db.session.commit()
        return existing_user, "PASSWORD_SET_ON_EXISTING", None
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] Failed to set password for {username}: {e}")
        return None, None, (jsonify({"status": "error", "message": "Unable to set password"}), 500)


# Audit logging moved to .helpers.log_audit


def _handle_password_and_user_flow(username, enrollment_count, real_pass, email, features):
    """Handle password validation/user creation logic across first and subsequent samples."""
    strength_result = calculate_password_strength(real_pass)
    features["password_strength"] = strength_result["strength"]
    features["password_score"] = strength_result["score"]

    # Weak password: log advisory only — do NOT block enrollment (UI already warns).
    if enrollment_count == 0 and strength_result["score"] < 0.5:
        print(
            f"[WARN] register_sample: weak password for '{username}' "
            f"(strength={strength_result['strength']}, score={strength_result['score']:.2f})"
        )

    user = None
    password_event = None

    # Subsequent samples: password must match existing
    if enrollment_count > 0:
        user = get_auth_service().get_user_by_username(username)
        if not user:
            return None, None, strength_result, (
                jsonify({"status": "error", "message": "User tidak ditemukan"}),
                404,
            )
        if not user.check_password(real_pass):
            return None, None, strength_result, (
                jsonify({
                    "status": "error",
                    "message": "Incorrect password",
                    "error_code": "PASSWORD_MISMATCH",
                }),
                400,
            )

    # First sample: create/validate user account
    if enrollment_count == 0:
        existing_user = get_auth_service().get_user_by_username(username)
        if existing_user:
            has_password = bool(getattr(existing_user, "password_hash", None))
            if has_password:
                if not existing_user.check_password(real_pass):
                    return None, None, strength_result, (
                        jsonify({
                            "status": "error",
                            "message": "Incorrect password",
                            "error_code": "PASSWORD_MISMATCH",
                        }),
                        400,
                    )
                user = existing_user
            else:
                # Server-side gate: a pending account can only be claimed by
                # someone who has proved ownership of its email. Trusting
                # `?verified=1` from the client is unsafe (response manipulation),
                # so the only thing we trust here is `email_verified=True` in DB.
                email_match = (
                    (email or "").strip().lower() == (existing_user.email or "").lower()
                    if email
                    else True
                )
                if not (existing_user.email_verified and email_match and existing_user.email):
                    return None, None, strength_result, (
                        jsonify({
                            "status": "error",
                            "message": "Email belum diverifikasi",
                            "error_code": "EMAIL_NOT_VERIFIED",
                        }),
                        403,
                    )
                user, password_event, set_pwd_error = _set_password_on_existing_user(
                    existing_user,
                    real_pass,
                    username,
                )
                if set_pwd_error:
                    return None, None, strength_result, set_pwd_error
        else:
            # No pending row for this username means /send_verification +
            # /verify_email was never completed. Block to enforce the
            # mandatory-verification policy server-side.
            return None, None, strength_result, (
                jsonify({
                    "status": "error",
                    "message": "Verifikasi email diperlukan sebelum registrasi",
                    "error_code": "EMAIL_VERIFICATION_REQUIRED",
                }),
                403,
            )

    return user, password_event, strength_result, None


def _resolve_enrollment_user_id(user, username):
    """Resolve user id for enrollment row, with fallback lookup by username."""
    if user:
        return getattr(user, "id", None)
    existing = get_auth_service().get_user_by_username(username)
    if existing:
        return getattr(existing, "id", None)
    return None


# Handled by consolidated helper in .helpers
pass


def _schedule_auto_training_if_ready(username, new_count):
    """Schedule background training when enrollment target is reached."""
    ml_training = None
    try:
        if new_count >= _recommended_samples():
            from flask import current_app

            app = current_app._get_current_object()  # type: ignore

            backend_name = str(current_app.config.get("ML_BACKEND", "rf") or "rf").strip().lower()
            backend_name = "svm" if backend_name == "svm" else "rf"

            if backend_name == "svm":
                from app.services.svm import (
                    schedule_background_training as schedule_background_training_backend,
                )
            else:
                from app.services.RF import (
                    schedule_background_training as schedule_background_training_backend,
                )

            started = schedule_background_training_backend(app, username, force=False)
            print(
                f"[AUTO-TRAIN] username={username} backend={backend_name} "
                f"status={'started' if started else 'already_running'}"
            )

            ml_training = {
                "success": True,
                "backend": backend_name,
                "reason": "training_started" if started else "training_in_progress",
                "message": (
                    f"{backend_name.upper()} model training started in background."
                    if started
                    else f"{backend_name.upper()} model training already in progress."
                ),
            }
    except Exception as _exc:
        ml_training = {
            "success": False,
            "reason": "auto_train_exception",
            "message": str(_exc),
        }

    return ml_training


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@api_bp.route("/check_username", methods=["POST"])
@_limiter.limit("60 per minute")
def check_username():
    """Check username availability for registration or login."""
    try:
        data = request.json
        username = (data.get("username", "") or "").strip()

        username, resolved_error = _resolve_username_for_check(username)
        if resolved_error:
            return resolved_error

        check_mode = data.get("mode", "register")

        if not username:
            return jsonify({
                "status": "error", "message": "Username tidak boleh kosong",
                "exists": False, "enrollment_complete": False, "enrollment_count": 0,
            }), 400

        availability = get_auth_service().check_username_availability(username)
        enrollment_status = get_biometric_service().get_enrollment_status(username)
        enrollment_count = enrollment_status["count"]
        login_ready = enrollment_status["ready_for_login"]

        print(f"[CHECK USERNAME] User: {username}, Mode: {check_mode}")
        print(f"  - Exists: {availability['exists']}, Enrollment: {enrollment_count}")

        # LOGIN MODE
        if check_mode == "login":
            return _build_check_username_login_response(
                username,
                availability,
                enrollment_count,
                login_ready,
            )

        # REGISTER MODE
        return _build_check_username_register_response(availability, enrollment_count)

    except Exception as e:
        print(f"[ERROR] check_username: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@api_bp.route("/register_sample", methods=["POST"])
@_limiter.limit("100 per minute")
def register_sample():
    """Register a single keystroke sample during enrollment."""
    try:
        data = request.json
        username, events, email = _extract_register_payload(data)

        payload_error = _validate_register_payload(username, events)
        if payload_error:
            return payload_error

        enrollment_status = get_biometric_service().get_enrollment_status(username)
        enrollment_count = enrollment_status["count"]

        _recommended_reg = _recommended_samples()
        if enrollment_count > 0:
            print(f"[INFO] User '{username}' continuing registration ({enrollment_count}/{_recommended_reg})")

        result, features, quality, prep_error_response, prep_error_code = _prepare_enrollment_features(
            username,
            events,
        )
        if prep_error_response:
            return prep_error_response, prep_error_code
            
        if not result or features is None or not quality:
            return jsonify({"status": "error", "message": "Failed to prepare features"}), 500

        real_pass = result.get("real_password_string")
        password_hash = result.get("password_hash")
        strength_result = None
        password_event = None
        user = None

        if real_pass:
            user, password_event, strength_result, password_flow_error = _handle_password_and_user_flow(
                username,
                enrollment_count,
                real_pass,
                email,
                features,
            )
            if password_flow_error:
                return password_flow_error
        else:
            features["password_strength"] = "unknown"
            features["password_score"] = 0
            strength_result = {"strength": "unknown", "score": 0}

        # Save enrollment sample via consolidated helper
        user_id = _resolve_enrollment_user_id(user, username)
        _, save_error = save_biometric_sample(username, user_id, features, password_hash)
        if save_error:
            return save_error
        
        db.session.commit()

        new_status = get_biometric_service().get_enrollment_status(username)
        new_count = new_status["count"]

        ml_training = _schedule_auto_training_if_ready(username, new_count)

        resp_payload = {
            "status": "success",
            "message": f"Sample {new_count}/{_recommended_reg} saved successfully",
            "progress": {
                "current": new_count, "target": _recommended_reg,
                "complete": new_status["ready_for_login"],
            },
            "quality": quality,
            "password_strength": {
                "strength": strength_result["strength"] if real_pass and strength_result else "unknown",
                "score": strength_result["score"] if real_pass and strength_result else 0,
                "label": get_strength_label(float(strength_result["score"])) if real_pass and strength_result else "Unknown",
            },
        }
        if ml_training is not None:
            resp_payload["ml_training"] = ml_training
        if password_event:
            resp_payload["password_event"] = password_event

        return jsonify(resp_payload)

    except Exception as e:
        print(f"[ERROR] register_sample: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500
