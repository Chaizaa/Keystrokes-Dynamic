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

import numpy as _np
from flask import current_app, jsonify, request, session
from flask_login import login_required, logout_user
from sqlalchemy import select

from app import limiter as _limiter
from app.models import AdminAudit, EnrollmentVector, KeystrokeVector, User, db
from app.utils.keystroke_processor import process_web_events

from ._shared import api_bp, auth_service, biometric_service, db_manager


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _fetch_enrollment_templates(username: str) -> list:
    """Return parsed enrollment templates from SQLAlchemy models.

    Tries EnrollmentVector first, then KeystrokeVector as fallback.
    Each template dict contains at minimum ``H_vector`` and ``DD_vector``.
    """

    def _parse(row) -> dict:
        t: dict = {}
        for key in ("H_vector", "DD_vector", "UD_vector", "UU_vector", "DU_vector"):
            val = getattr(row, key, None)
            if val:
                try:
                    t[key] = json.loads(val)
                except Exception:
                    try:
                        t[key] = eval(val)  # noqa: S307
                    except Exception:
                        t[key] = []
            else:
                t[key] = []
        # Carry the SHA-256 password hash for Verifier's hash pre-check
        ph = getattr(row, "password_hash", None)
        if ph:
            t["password_hash"] = ph
        return t

    templates: list = []

    try:
        rows = db.session.execute(
            select(EnrollmentVector).where(EnrollmentVector.username == username)
        ).scalars().all()
        templates = [_parse(r) for r in rows]
    except Exception:
        templates = []

    if not templates:
        try:
            rows = db.session.execute(
                select(KeystrokeVector).where(
                    KeystrokeVector.username == username,
                    (KeystrokeVector.event_type == "enrollment")
                    | (KeystrokeVector.data_type == "enrollment"),
                )
            ).scalars().all()
            templates = [_parse(r) for r in rows]
        except Exception:
            templates = []

    return templates


# ---------------------------------------------------------------------------
# Biometric verification using all 5 timing vectors via Verifier
# ---------------------------------------------------------------------------

def _verify_biometric(username: str, login_sample: dict, templates: list) -> dict:
    """Verify identity using Verifier.extract_statistical_features on all 5 vectors.

    Produces a 35-feature vector (7 stats × 5 timing vectors: H, DD, UD, UU, DU)
    for both the login sample and every enrollment template, then measures the
    Euclidean distance of the login vector to the mean enrollment profile.

    Threshold is adaptive: mean intra-class distance + 2σ (covers ~95% of genuine
    users without hard-coding a constant).
    """
    from verifier import Verifier as _Verifier

    min_needed = biometric_service.MIN_SAMPLES_FOR_VERIFICATION
    if not templates or len(templates) < min_needed:
        return {
            "success": False,
            "verified": False,
            "score": 0.0,
            "reason": "insufficient_samples",
            "message": f"Need at least {min_needed} enrollment samples",
        }

    verifier = _Verifier()

    # 35-feature statistical vectors from enrollment templates
    enrollment_vecs = []
    for t in templates:
        try:
            fv = verifier.extract_statistical_features(t)
            if fv is not None and len(fv) == 35:
                # Replace NaN (e.g. skew/kurtosis of constant vectors) with 0
                fv = _np.where(_np.isnan(fv), 0.0, fv)
                enrollment_vecs.append(fv)
        except Exception:
            continue

    if len(enrollment_vecs) < min_needed:
        return {
            "success": False,
            "verified": False,
            "score": 0.0,
            "reason": "insufficient_valid_templates",
            "message": "Insufficient valid enrollment templates after feature extraction",
        }

    # 35-feature statistical vector from login sample
    try:
        login_vec = verifier.extract_statistical_features(login_sample)
    except Exception as e:
        print(f"[ERROR] _verify_biometric feature extraction: {e}")
        return {"success": False, "verified": False, "score": 0.0,
                "reason": "feature_extraction_failed"}

    if login_vec is None or len(login_vec) != 35:
        return {"success": False, "verified": False, "score": 0.0,
                "reason": "invalid_login_features"}
    # Replace NaN in login vector too
    login_vec = _np.where(_np.isnan(login_vec), 0.0, login_vec)

    Y_train = _np.array(enrollment_vecs, dtype=float)
    mean_vec = _np.mean(Y_train, axis=0)

    # Adaptive threshold: mean intra-class distance + 2 standard deviations
    intra_dists = [float(_np.linalg.norm(row - mean_vec)) for row in Y_train]
    mean_intra = float(_np.mean(intra_dists))
    std_intra = float(_np.std(intra_dists))
    threshold_dist = mean_intra + 2.0 * std_intra

    login_dist = float(_np.linalg.norm(login_vec - mean_vec))

    # Normalised score: higher = more similar to enrollment profile
    score = float(1.0 / (1.0 + login_dist))
    is_genuine = login_dist <= threshold_dist

    confidence_label = (
        "high" if login_dist <= mean_intra
        else "medium" if login_dist <= mean_intra + std_intra
        else "low" if is_genuine
        else "failed"
    )

    print(
        f"[BIOMETRIC] {username} | dist={login_dist:.4f} | "
        f"threshold={threshold_dist:.4f} (mean={mean_intra:.4f} std={std_intra:.4f}) | "
        f"score={score:.4f} | {'PASS' if is_genuine else 'FAIL'}"
    )

    return {
        "success": True,
        "verified": is_genuine,
        "score": round(score, 4),
        "distance": round(login_dist, 4),
        "threshold_dist": round(threshold_dist, 4),
        "confidence": confidence_label,
        "templates_used": len(enrollment_vecs),
        "message": (
            "Biometric verification successful"
            if is_genuine
            else "Biometric verification failed"
        ),
    }


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

        # Biometric verification using all 5 timing vectors (H, DD, UD, UU, DU)
        templates = _fetch_enrollment_templates(username)
        verification_result = _verify_biometric(username, features, templates)
        print(f"[LOGIN] {username} biometric => verified={verification_result.get('verified')} "
              f"score={verification_result.get('score')} "
              f"templates={verification_result.get('templates_used')}")

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
            "data_type": "verification",
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
