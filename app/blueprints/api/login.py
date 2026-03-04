"""
Login / biometric verification endpoints.

Routes
------
POST /api/pre_verify_password
POST /api/login
POST /api/verify_user
"""

import json
import traceback
from datetime import datetime, timezone

from flask import current_app, jsonify, request, session
from flask_login import login_required, logout_user
from sqlalchemy import select

from app import limiter as _limiter
from app.models import AdminAudit, EnrollmentVector, KeystrokeVector, User, db
from app.services.ml_biometric_service import MLBiometricService
from app.utils.keystroke_processor import process_web_events

from ._shared import api_bp, auth_service, biometric_service, db_manager


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@api_bp.route("/pre_verify_password", methods=["POST"])
def pre_verify_password():
    """Pre-verify password before collection / verification mode."""
    try:
        data = request.json
        username = data.get("username")
        raw_events = data.get("events")

        if not username or not raw_events:
            return jsonify({"valid": False, "message": "Data tidak lengkap"}), 400

        enrollment_data = db_manager.get_enrollment_samples(username)
        if not enrollment_data or len(enrollment_data) == 0:
            return jsonify({"valid": False, "message": "User not registered"}), 404

        result = process_web_events(raw_events, username)
        if result["status"] != "success":
            return jsonify({"valid": False,
                            "message": "Failed to process keystroke data"}), 400

        features = result["features"]
        password_hash = result.get("password_hash", "")
        stored_hash = db_manager.get_password_hash(username)

        if stored_hash:
            print(f"[Pre-Verify] User '{username}' → Tier 2 (Hash + Keystroke)")
            if password_hash != stored_hash:
                return jsonify({"valid": False,
                                "message": "Incorrect password",
                                "reason": "hash_mismatch"}), 403
            keystroke_threshold = 0.2
            tier_label = "Hash+Keystroke"
        else:
            print(f"[Pre-Verify] User '{username}' → Tier 1 (Keystroke Only)")
            keystroke_threshold = 0.4
            tier_label = "Keystroke Only (LEGACY)"

        verification_result = biometric_service.verify_keystroke_sample(
            username, features, use_statistical=False
        )
        if not verification_result.get("success"):
            return jsonify({"valid": False,
                            "message": verification_result.get("message", "Verification error"),
                            "reason": verification_result.get("reason", "verification_error")}), 400

        score = float(verification_result.get("score", 0.0))
        is_genuine = score >= keystroke_threshold
        print(f"[Pre-Verify] {tier_label} | Score: {score:.4f} | "
              f"Result: {'PASS' if is_genuine else 'FAIL'}")

        if not is_genuine:
            return jsonify({
                "valid": False,
                "message": f"Ritme ketikan tidak cocok (score: {score:.3f})",
                "reason": "keystroke_mismatch",
                "score": score,
                "threshold": keystroke_threshold,
                "security_tier": "modern" if stored_hash else "legacy",
            }), 403

        return jsonify({
            "valid": True,
            "message": "Pre-verification berhasil",
            "score": score,
            "threshold": keystroke_threshold,
            "security_tier": "modern" if stored_hash else "legacy",
        }), 200

    except Exception as e:
        print(f"[ERROR] Pre-verification: {e}")
        traceback.print_exc()
        return jsonify({"valid": False, "message": f"Server Error: {str(e)}"}), 500


@api_bp.route("/login", methods=["POST"])
@_limiter.limit("10 per minute")
def login():
    """Unified login endpoint with comprehensive biometric verification."""
    try:
        data = request.json
        identifier = (data.get("username", "") or "").strip()
        user_obj = auth_service.get_user_by_identifier(identifier)
        username = user_obj.username if user_obj else identifier
        events = data.get("events")
        ip_address = request.remote_addr
        user_agent = request.headers.get("User-Agent", "Unknown")

        if not username or not events:
            return jsonify({"success": False, "message": "Data tidak lengkap",
                            "reason": "invalid_input"}), 400

        # Application-level rate limiting
        recent_failed = db_manager.get_failed_login_count_recent(username, minutes=15)
        DEV_LENIENT = current_app.config.get("DEV_LENIENT_RATELIMIT", False)
        if recent_failed >= 5 and not DEV_LENIENT:
            db_manager.log_failed_login(username, "rate_limit_exceeded",
                                        ip_address, user_agent)
            return jsonify({"success": False, "message": "Coba lagi nanti",
                            "reason": "rate_limit_exceeded"}), 429
        if recent_failed >= 5 and DEV_LENIENT:
            db_manager.log_failed_login(username, "rate_limit_skipped_dev",
                                        ip_address, user_agent)
            print(f"[DEV] Skipping rate-limit lockout for {username} in DEV_LENIENT mode")

        # Extract keystroke features
        result = process_web_events(events, username)
        if result["status"] == "error":
            db_manager.log_failed_login(username, "invalid_keystroke_data",
                                        ip_address, user_agent)
            return jsonify({"success": False, "message": "Keystroke data tidak valid",
                            "reason": "invalid_data"}), 400

        features = result["features"]

        # Password check — unconditional bcrypt (user_obj already resolved at top of route)
        real_pass = result.get("real_password_string")
        if user_obj and getattr(user_obj, "password_hash", None):
            if real_pass is None or not user_obj.check_password(real_pass):
                db_manager.log_failed_login(username, "password_mismatch",
                                            ip_address, user_agent)
                return jsonify({"success": False, "message": "Incorrect password",
                                "reason": "PASSWORD_MISMATCH"}), 403

        # Enrollment status
        enrollment_status = biometric_service.get_enrollment_status(username)
        enrollment_count = enrollment_status["count"]

        if enrollment_count == 0:
            db_manager.log_failed_login(username, "no_enrollment", ip_address, user_agent)
            return jsonify({"success": False, "message": "User not registered",
                            "reason": "no_enrollment"}), 404

        # ML-based biometric verification
        if enrollment_status.get("ready_for_login"):
            try:
                db_path = current_app.config.get("DATABASE_PATH")
                ml_service = MLBiometricService(db_path)

                ml_result = ml_service.verify(
                    username=username,
                    sample=features,
                )

                verification_result = {
                    "success": True,
                    "verified": bool(ml_result.get("verified", False)),
                    "score": float(ml_result.get("score", 0.0)),
                    "confidence": ml_result.get("confidence"),
                    "method": "random_forest",
                    "templates_used": ml_result.get("samples_used", enrollment_count),
                }

            except Exception as e:
                print(f"[ML VERIFY ERROR] {e}")
                verification_result = {
                    "success": False,
                    "verified": False,
                    "score": 0.0,
                    "error": "ml_verification_error",
                }
        else:
            verification_result = {
                "success": False,
                "verified": False,
                "score": 0.0,
                "error": "insufficient_enrollment",
                "reason": "insufficient_enrollment",
            }

        print(f"[LOGIN] {username} biometric => verified={verification_result.get('verified')} "
              f"score={verification_result.get('score')} "
              f"method={verification_result.get('method', 'unknown')}")

        if not verification_result.get("verified"):
            conf_score = float(verification_result.get("score", 0.0))
            if DEV_LENIENT and conf_score >= (biometric_service.MEDIUM_CONFIDENCE_THRESHOLD - 0.05):
                verification_result["verified"] = True
                verification_result["success"] = True
                verification_result["relaxed_verification"] = True
                print(f"[DEV] Relaxed verification for {username}: score={conf_score}")
            else:
                if not enrollment_status["ready_for_login"]:
                    db_manager.log_failed_login(username, "insufficient_enrollment",
                                                ip_address, user_agent)
                    payload = {
                        "success": False,
                        "message": f"Enrollment belum lengkap ({enrollment_count}/20)",
                        "reason": "insufficient_enrollment",
                    }
                    if (request.json or {}).get("debug") or DEV_LENIENT:
                        payload["debug"] = verification_result
                    return jsonify(payload), 400
                else:
                    db_manager.log_failed_login(username, "impostor_detected",
                                                ip_address, user_agent)
                    payload = {"success": False, "message": "Verification failed",
                               "reason": "impostor_detected"}
                    if (request.json or {}).get("debug") or DEV_LENIENT:
                        payload["debug"] = verification_result
                    return jsonify(payload), 403

        # Re-fetch User for flask-login session creation
        user = db.session.execute(
            select(User).where(User.username == username)
        ).scalars().first()
        if not user:
            db_manager.log_failed_login(username, "user_not_found", ip_address, user_agent)
            return jsonify({"success": False, "message": "User tidak ditemukan",
                            "reason": "user_not_found"}), 404

        # 2FA check before full login
        if user.two_factor_enabled and enrollment_status.get("ready_for_login"):
            session["2fa_user_id"] = user.id
            logout_user()
            return jsonify({"success": True, "requires_2fa": True,
                            "message": "2FA verification required",
                            "redirect": "/auth/2fa/verify"}), 200

        # Email verification required (non-admin)
        if not user.is_admin() and user.email and not user.email_verified:
            db_manager.log_failed_login(username, "email_not_verified",
                                        ip_address, user_agent)
            return jsonify({"success": False,
                            "message": "Email not verified. Check your inbox",
                            "reason": "email_not_verified",
                            "requires_verification": True}), 403

        # Ensure success flag is consistent
        if verification_result.get("verified") and not verification_result.get("success"):
            verification_result["success"] = True

        is_genuine = verification_result["verified"]
        confidence_score = float(verification_result.get("score", 0.0))

        if is_genuine:
            db_manager.save_verified_login({
                "username": username,
                "password_hash": user.password_hash,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "verification_score": confidence_score,
                "recommended_method": verification_result.get("confidence", "medium"),
                "ip_address": ip_address,
                "user_agent": user_agent,
            })

            login_result = auth_service.login_user_session(user)
            if not login_result:
                return jsonify({"success": False, "message": "Failed to create session",
                                "reason": "session_error"}), 500

            if user.two_factor_enabled:
                session["2fa_user_id"] = user.id
                logout_user()
                return jsonify({"success": True, "requires_2fa": True,
                                "message": "2FA verification required",
                                "redirect": "/auth/2fa/verify"}), 200

            user.last_login = datetime.now(timezone.utc)
            user.last_login_ip = ip_address
            db.session.commit()

            try:
                AdminAudit.log(
                    action=AdminAudit.ACTION_LOGIN,
                    user_id=user.id, username=user.username,
                    details={"ip": ip_address, "score": confidence_score},
                )
                db.session.commit()
            except Exception:
                pass

            return jsonify({
                "success": True,
                "message": "Login successful",
                "score": confidence_score,
                "confidence_label": verification_result.get("confidence", "medium"),
                "templates_used": verification_result.get("templates_used", 0),
            }), 200

        else:
            db_manager.log_failed_login(username, "impostor_detected",
                                        ip_address, user_agent,
                                        verification_score=confidence_score)
            return jsonify({
                "success": False, "message": "Login failed",
                "reason": "impostor_detected",
                "score": confidence_score,
                "confidence_label": verification_result.get("confidence", "low"),
            }), 403

    except Exception as e:
        print(f"[ERROR] Login failed: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": f"Server Error: {str(e)}",
                        "reason": "server_error"}), 500


@api_bp.route("/verify_user", methods=["POST"])
def verify_user():
    """Verify user with comprehensive biometric analysis."""
    try:
        data = request.json
        username = data.get("username")
        events = data.get("events")

        if not events or not username:
            return jsonify({"message": "Data tidak lengkap"}), 400

        process_result = process_web_events(events, username)
        if process_result["status"] == "error":
            return jsonify({"status": "error",
                            "message": process_result["msg"]}), 400

        new_features = process_result["features"]
        enrollment_data = db_manager.get_enrollment_samples(username)

        if len(enrollment_data) < 5:
            return jsonify({
                "status": "error",
                "message": (f"User not registered or enrollment data insufficient "
                            f"({len(enrollment_data)} samples)"),
            }), 404

        verification_result = biometric_service.verify_keystroke_sample(username, new_features)
        if not verification_result.get("success"):
            return jsonify({"status": "error",
                            "message": verification_result.get("message",
                                                               "Verification error")}), 400

        # Save verification record
        new_features.update({
            "username": username,
            "login_result": str(verification_result["verified"]),
            "login_score": verification_result["score"],
            "event_type": "verification",
        })
        db_manager.save_data(new_features)

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
