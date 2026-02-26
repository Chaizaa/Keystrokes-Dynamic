"""
Enrollment (registration) endpoints.

Routes
------
POST /api/check_username
POST /api/register_sample
"""

import json
import traceback
from datetime import datetime, timezone

from flask import jsonify, request

from app import limiter as _limiter
from app.models import AdminAudit, EnrollmentVector, User, db
from app.services.email_service import email_service
from app.utils.keystroke_processor import assess_sample_quality, process_web_events
from app.utils.password_strength import calculate_password_strength, get_strength_label

from ._shared import api_bp, auth_service, biometric_service, db_manager


# ---------------------------------------------------------------------------
# Helper: write stats flat dict → model columns
# ---------------------------------------------------------------------------

def _apply_vector_stats(ev, features: dict) -> None:
    """Copy flat timing stats from the features dict onto an EnrollmentVector instance.

    Uses the flat keys produced by ``process_web_events`` (H_mean, H_std, …, H_cv, etc.)
    which are now populated by ``compute_vector_stats`` inside the processor.
    """
    for prefix in ("H", "DD", "UD", "UU", "DU"):
        for stat in ("mean", "std", "min", "max", "cv"):
            col = f"{prefix}_{stat}"
            val = features.get(col)
            if val is not None:
                setattr(ev, col, val)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@api_bp.route("/check_username", methods=["POST"])
@_limiter.limit("10 per minute")
def check_username():
    """Check username availability for registration or login."""
    try:
        data = request.json
        username = (data.get("username", "") or "").strip()

        # Support email lookup
        try:
            if "@" in username:
                user_obj = auth_service.get_user_by_email(username)
                if user_obj:
                    username = user_obj.username
                else:
                    return jsonify({
                        "exists": False, "can_login": False,
                        "enrollment_complete": False, "enrollment_count": 0,
                        "message": f"User {username} tidak ditemukan",
                    }), 200
        except Exception:
            pass

        check_mode = data.get("mode", "register")

        if not username:
            return jsonify({
                "status": "error", "message": "Username tidak boleh kosong",
                "exists": False, "enrollment_complete": False, "enrollment_count": 0,
            }), 400

        availability = auth_service.check_username_availability(username)
        enrollment_status = biometric_service.get_enrollment_status(username)
        enrollment_count = enrollment_status["count"]
        login_ready = enrollment_status["ready_for_login"]

        print(f"[CHECK USERNAME] User: {username}, Mode: {check_mode}")
        print(f"  - Exists: {availability['exists']}, Enrollment: {enrollment_count}")

        # LOGIN MODE
        if check_mode == "login":
            if not availability["exists"]:
                return jsonify({
                    "exists": False, "can_login": False,
                    "enrollment_complete": False, "enrollment_count": 0,
                    "message": f"User {username} tidak ditemukan",
                }), 200
            return jsonify({
                "exists": True, "can_login": login_ready,
                "enrollment_complete": login_ready, "enrollment_count": enrollment_count,
                "message": (f"User {username} ditemukan" if login_ready
                            else f"Enrollment belum lengkap ({enrollment_count}/20)"),
            }), 200

        # REGISTER MODE
        if availability.get("exists") and 0 < enrollment_count < 20:
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
            "detail": "",
        }

        if status_str == "resumable" and availability.get("exists"):
            response_data["message"] = (
                f"Resume registration: {enrollment_count}/20 samples collected"
            )

        return jsonify(response_data)

    except Exception as e:
        print(f"[ERROR] check_username: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@api_bp.route("/register_sample", methods=["POST"])
@_limiter.limit("30 per minute")
def register_sample():
    """Register a single keystroke sample during enrollment."""
    try:
        data = request.json
        username = (data.get("username") or "").strip()
        events = data.get("events")
        raw_email = data.get("email", None)
        email = raw_email.strip() or None if isinstance(raw_email, str) else None

        if not events or not username:
            return jsonify({"status": "error", "message": "Data tidak lengkap"}), 400

        validation = auth_service.validate_username(username)
        if not validation["valid"]:
            return jsonify({"status": "error", "message": validation["message"]}), 400

        enrollment_status = biometric_service.get_enrollment_status(username)
        enrollment_count = enrollment_status["count"]

        if enrollment_count > 0:
            print(f"[INFO] User '{username}' continuing registration ({enrollment_count}/20)")

        result = process_web_events(events, username)
        if result["status"] != "success":
            return jsonify({"status": "error", "message": result["msg"]}), 400

        features = result["features"]
        features["username"] = username
        features["data_type"] = "enrollment"

        quality = assess_sample_quality(features)
        features["quality_label"] = quality["quality_label"]
        features["quality_score"] = quality["quality_score"]

        real_pass = result.get("real_password_string")
        password_hash = result.get("password_hash")
        strength_result = None
        password_event = None

        if real_pass:
            strength_result = calculate_password_strength(real_pass)
            features["password_strength"] = strength_result["strength"]
            features["password_score"] = strength_result["score"]

            # Weak password: log advisory only — do NOT block enrollment (UI already warns).
            if enrollment_count == 0 and strength_result["score"] < 0.5:
                print(f"[WARN] register_sample: weak password for '{username}' "
                      f"(strength={strength_result['strength']}, score={strength_result['score']:.2f})")

            # Subsequent samples: password must match existing
            if enrollment_count > 0:
                user = auth_service.get_user_by_username(username)
                if not user:
                    return jsonify({"status": "error",
                                    "message": "User tidak ditemukan"}), 404
                if not user.check_password(real_pass):
                    return jsonify({"status": "error", "message": "Incorrect password",
                                    "error_code": "PASSWORD_MISMATCH"}), 400

            # First sample: create/validate user account
            if enrollment_count == 0:
                existing_user = auth_service.get_user_by_username(username)
                if existing_user:
                    has_password = bool(getattr(existing_user, "password_hash", None))
                    if has_password:
                        if not existing_user.check_password(real_pass):
                            return jsonify({"status": "error", "message": "Incorrect password",
                                            "error_code": "PASSWORD_MISMATCH"}), 400
                        user = existing_user
                    else:
                        try:
                            existing_user.set_password(real_pass)
                            db.session.commit()
                            user = existing_user
                            password_event = "PASSWORD_SET_ON_EXISTING"
                        except Exception as e:
                            db.session.rollback()
                            print(f"[ERROR] Failed to set password for {username}: {e}")
                            return jsonify({"status": "error",
                                            "message": "Unable to set password"}), 500
                else:
                    user_result = auth_service.create_user(username, real_pass, email=email)
                    if not user_result["success"]:
                        err_payload = {"status": "error",
                                       "message": user_result.get("message",
                                                                   "Unable to create account")}
                        if user_result.get("error_code"):
                            err_payload["error_code"] = user_result["error_code"]
                        return jsonify(err_payload), 400

                    user = user_result.get("user")

                    # Audit: registration
                    try:
                        if user:
                            AdminAudit.log(
                                action=AdminAudit.ACTION_REGISTERED,
                                user_id=user.id, username=user.username,
                                details={"email": user.email},
                            )
                            db.session.commit()
                    except Exception:
                        pass

                    if user:
                        try:
                            features["user_id"] = int(user.id)
                        except Exception:
                            pass

                    # Send verification email if email provided
                    if user and user.email and email and "@" in email:
                        user = db.session.get(User, user.id)
                        try:
                            sent_at = datetime.now(timezone.utc)
                            user.email_verification_sent_at = sent_at
                            db.session.commit()
                            try:
                                token = email_service.generate_token(
                                    user.email, salt="email-verify", sent_at=sent_at)
                            except TypeError:
                                token = email_service.generate_token(
                                    user.email, salt="email-verify")
                            email_service.send_verification_email(user, token)
                            print(f"[INFO] Verification email sent to {user.email}")
                        except Exception as e:
                            print(f"[WARNING] Failed to send verification email: {e}")
        else:
            features["password_strength"] = "unknown"
            features["password_score"] = 0

        # Save enrollment vector via SQLAlchemy
        try:
            uid = None
            if "user" in locals() and locals().get("user"):
                uid = getattr(locals()["user"], "id", None)
            else:
                existing = auth_service.get_user_by_username(username)
                if existing:
                    uid = getattr(existing, "id", None)

            if uid is not None:
                features["user_id"] = int(uid)
                ev = EnrollmentVector(username=username, data_type="enrollment")
                ev.timestamp = datetime.now(timezone.utc).isoformat()
                ev.total_duration = features.get("total_duration")
                ev.typing_speed = features.get("typing_speed")

                # Raw vectors
                for vec_name in ("H", "DD", "UD", "UU", "DU"):
                    setattr(ev, f"{vec_name}_vector",
                            json.dumps(features.get(f"{vec_name}_vector", [])))

                # Flat stats (mean, std, min, max, cv) – filled by _apply_vector_stats
                _apply_vector_stats(ev, features)

                if password_hash:
                    ev.password_hash = password_hash

                db.session.add(ev)
                db.session.commit()
            else:
                if db_manager.save_data(features) is False:
                    print(f"[ERROR] register_sample: DB save failed for user {username}")
                    return jsonify({"status": "error",
                                    "message": "Database error saving sample"}), 500

        except Exception as e:
            print(f"[ERROR] register_sample save_data: {e}")
            traceback.print_exc()
            return jsonify({"status": "error",
                            "message": "Database error saving sample"}), 500

        new_status = biometric_service.get_enrollment_status(username)
        new_count = new_status["count"]

        resp_payload = {
            "status": "success",
            "message": f"Sample {new_count}/20 saved successfully",
            "progress": {
                "current": new_count, "target": 20,
                "complete": new_status["ready_for_login"],
            },
            "quality": quality,
            "password_strength": {
                "strength": strength_result["strength"] if real_pass else "unknown",
                "score": strength_result["score"] if real_pass else 0,
                "label": get_strength_label(strength_result["score"]) if real_pass else "Unknown",
            },
        }
        if password_event:
            resp_payload["password_event"] = password_event

        return jsonify(resp_payload)

    except Exception as e:
        print(f"[ERROR] register_sample: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500
