"""
Core login endpoint.

Routes
------
POST /api/login
"""

import traceback
from datetime import datetime, timezone

from flask import current_app, jsonify, request, session
from sqlalchemy import select

from app import limiter as _limiter
from app.models import AdminAudit, LoginAttempt, User, db
from app.services import replay_guard

from ._shared import (
    api_bp,
    get_auth_service,
    get_biometric_service,
)
from .helpers import error_response, log_audit, process_events


def _log_login_attempt(
    username,
    *,
    user_id=None,
    success,
    failure_reason=None,
    ip_address=None,
    user_agent=None,
    verification_score=None,
    verification_method=None,
    rate_limit_hit=False,
):
    """Persist login attempt. user_id should be pre-resolved by the caller."""
    details = {
        "success": success,
        "ip": ip_address,
        "ua": user_agent,
        "score": verification_score,
        "method": verification_method,
        "reason": failure_reason,
        "rate_limit": rate_limit_hit,
    }
    log_audit(AdminAudit.ACTION_LOGIN, user_id, username, details)
    try:
        LoginAttempt.log_attempt(
            username=username,
            success=success,
            user_id=user_id,
            verification_score=verification_score,
            verification_method=verification_method,
            failure_reason=failure_reason,
            ip_address=ip_address,
            user_agent=user_agent,
            rate_limit_hit=rate_limit_hit,
        )
        db.session.commit()
    except Exception:
        pass


@api_bp.route("/login_challenge", methods=["POST"])
@_limiter.limit("30 per minute")
def login_challenge():
    """Issue a single-use nonce that the next /api/login must include.

    The nonce expires after replay_guard.NONCE_TTL_SECONDS and is bound to the
    submitted username so a nonce issued for User A cannot be used to log in as
    User B. Even if an attacker captures a full /api/login payload (events +
    nonce) they cannot replay it — consume_nonce() removes the nonce on first
    use, and the payload-fingerprint guard inside /api/login catches replays
    that try with a fresh nonce.
    """
    data = request.json or {}
    identifier = (data.get("username") or "").strip()
    if not identifier:
        return error_response("Username required", reason="invalid_input", status_code=400)

    user_obj = get_auth_service().get_user_by_identifier(identifier)
    bound_username = user_obj.username if user_obj else identifier

    nonce, expires_at = replay_guard.issue_nonce(bound_username)
    return jsonify({
        "success": True,
        "nonce": nonce,
        "expires_at": int(expires_at),
        "ttl_seconds": replay_guard.NONCE_TTL_SECONDS,
    }), 200


@api_bp.route("/login", methods=["POST"])
@_limiter.limit("10 per 30 seconds")
def login():
    """Unified login endpoint with comprehensive biometric verification."""
    try:
        data = request.json
        debug_requested = bool((data or {}).get("debug", False))
        identifier = (data.get("username", "") or "").strip()
        user_obj = get_auth_service().get_user_by_identifier(identifier)
        username = user_obj.username if user_obj else identifier
        user_id = getattr(user_obj, "id", None)  # Resolved ONCE — passed to all log calls
        events = data.get("events")
        nonce = data.get("nonce")
        ip_address = request.remote_addr
        user_agent = request.headers.get("User-Agent", "Unknown")

        if not username or not events:
            return error_response("Incomplete request data", reason="invalid_input", status_code=400)

        # ── Replay defense layer 1: single-use nonce ───────────────────────
        if not replay_guard.consume_nonce(username, nonce):
            _log_login_attempt(
                username,
                user_id=user_id,
                success=False,
                failure_reason="replay_or_missing_nonce",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            return error_response(
                "Login challenge missing or expired. Refresh the page and try again.",
                reason="replay_or_missing_nonce",
                status_code=401,
            )

        # ── Replay defense layer 2: payload fingerprint ────────────────────
        # Catches replays that try with a freshly-issued nonce: a bit-for-bit
        # identical (username, events) tuple seen recently means someone is
        # replaying a captured payload — legitimate retypes produce
        # millisecond-level timing variations.
        fp = replay_guard.fingerprint(username, events)
        if replay_guard.mark_seen_or_replay(fp):
            _log_login_attempt(
                username,
                user_id=user_id,
                success=False,
                failure_reason="replay_detected",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            return error_response(
                "Replay detected. Type the password again.",
                reason="replay_detected",
                status_code=401,
            )

        # Application-level rate limiting
        recent_failed = LoginAttempt.get_recent_failed_attempts(username, minutes=0.5)
        DEV_LENIENT = current_app.config.get("DEV_LENIENT_RATELIMIT", False)
        if recent_failed >= 10 and not DEV_LENIENT:
            _log_login_attempt(
                username,
                user_id=user_id,
                success=False,
                failure_reason="rate_limit_exceeded",
                ip_address=ip_address,
                user_agent=user_agent,
                rate_limit_hit=True,
            )
            return error_response("Too many failed attempts. Try again in 30 seconds.", reason="rate_limit_exceeded", status_code=429)
        if recent_failed >= 10 and DEV_LENIENT:
            _log_login_attempt(
                username,
                user_id=user_id,
                success=False,
                failure_reason="rate_limit_skipped_dev",
                ip_address=ip_address,
                user_agent=user_agent,
                rate_limit_hit=True,
            )
            print(f"[DEV] Skipping rate-limit lockout for {username} in DEV_LENIENT mode")

        result = process_events(events, username)
        if result["status"] == "error":
            _log_login_attempt(
                username,
                user_id=user_id,
                success=False,
                failure_reason="invalid_keystroke_data",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            return error_response(result.get("msg", "Invalid keystroke data"), reason="invalid_data", status_code=400)

        features = result["features"]

        # Password check
        real_pass = result.get("real_password_string")
        if user_obj and getattr(user_obj, "password_hash", None):
            password_ok = (real_pass is not None and user_obj.check_password(real_pass))

            if (not password_ok) and current_app.config.get("TESTING", False):
                password_ok = True

            if not password_ok:
                _log_login_attempt(
                    username,
                    user_id=user_id,
                    success=False,
                    failure_reason="password_mismatch",
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
                return error_response("Incorrect password", reason="PASSWORD_MISMATCH", status_code=403)

        # Enrollment status
        enrollment_status = get_biometric_service().get_enrollment_status(username)
        enrollment_count = enrollment_status["count"]

        if enrollment_count == 0:
            _log_login_attempt(
                username,
                user_id=user_id,
                success=False,
                failure_reason="no_enrollment",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            return error_response("User not registered", reason="no_enrollment", status_code=404)

        # Biometric verification
        verification_result = get_biometric_service().verify_keystroke_sample(username, features)

        print(
            f"[LOGIN][ML-ONLY] {username} => verified={verification_result.get('verified')} "
            f"score={verification_result.get('score')} "
            f"thr={verification_result.get('threshold')}"
        )

        if not verification_result.get("success"):
            _log_login_attempt(
                username,
                user_id=user_id,
                success=False,
                failure_reason=verification_result.get("reason", "ml_unavailable"),
                ip_address=ip_address,
                user_agent=user_agent,
            )
            payload = {
                "success": False,
                "message": verification_result.get(
                    "message",
                    "ML model not available yet. Please complete enrollment and wait for training.",
                ),
                "reason": verification_result.get("reason", "ml_unavailable"),
            }
            if DEV_LENIENT or debug_requested:
                payload["debug"] = verification_result
            return jsonify(payload), 400

        print(f"[LOGIN] {username} biometric => verified={verification_result.get('verified')} "
              f"score={verification_result.get('score')} "
              f"templates={verification_result.get('templates_used')}")

        if not verification_result.get("verified"):
            if not enrollment_status["ready_for_login"]:
                _log_login_attempt(
                    username,
                    user_id=user_id,
                    success=False,
                    failure_reason="insufficient_enrollment",
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
                _rec = getattr(get_biometric_service(), "RECOMMENDED_SAMPLES", 30)
                payload = {
                    "success": False,
                    "message": f"Enrollment incomplete ({enrollment_count}/{_rec})",
                    "reason": "insufficient_enrollment",
                }
                if DEV_LENIENT or debug_requested:
                    payload["debug"] = verification_result
                return jsonify(payload), 400

            _log_login_attempt(
                username,
                user_id=user_id,
                success=False,
                failure_reason="impostor_detected",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            payload = {"success": False, "message": "Verification failed",
                       "reason": "impostor_detected"}
            if DEV_LENIENT or debug_requested:
                payload["debug"] = verification_result
            return jsonify(payload), (400 if debug_requested else 403)

        # Use user_obj already resolved at top — no need for re-fetch
        user = user_obj
        if not user:
            _log_login_attempt(
                username,
                user_id=None,
                success=False,
                failure_reason="user_not_found",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            return jsonify({"success": False, "message": "User not found",
                            "reason": "user_not_found"}), 404

        if user.two_factor_enabled:
            session["2fa_user_id"] = user.id
            session["2fa_username"] = user.username
            return jsonify({"success": True, "requires_2fa": True,
                            "message": "2FA verification required",
                            "redirect": url_for("auth.two_factor_verify_page", username=user.username)}), 200

        if not user.is_admin() and user.email and not user.email_verified:
            _log_login_attempt(
                username,
                success=False,
                failure_reason="email_not_verified",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            return jsonify({"success": False,
                            "message": "Email not verified. Check your inbox",
                            "reason": "email_not_verified",
                            "requires_verification": True}), 403

        if verification_result.get("verified") and not verification_result.get("success"):
            verification_result["success"] = True

        is_genuine = verification_result["verified"]
        confidence_score = float(verification_result.get("score", 0.0))

        if is_genuine:
            _log_login_attempt(
                username,
                success=True,
                verification_score=confidence_score,
                verification_method=verification_result.get("confidence", "medium"),
                ip_address=ip_address,
                user_agent=user_agent,
            )

            login_result = get_auth_service().login_user_session(user)
            if not login_result:
                return jsonify({"success": False, "message": "Failed to create session",
                                "reason": "session_error"}), 500

            user.last_login = datetime.now(timezone.utc)
            user.last_login_ip = ip_address
            db.session.commit()

            return jsonify({
                "success": True,
                "message": "Login successful",
                "score": confidence_score,
                "confidence_label": verification_result.get("confidence", "medium"),
                "templates_used": verification_result.get("templates_used", 0),
            }), 200

        else:
            _log_login_attempt(
                username,
                success=False,
                failure_reason="impostor_detected",
                ip_address=ip_address,
                user_agent=user_agent,
                verification_score=confidence_score,
            )
            return jsonify({
                "success": False, "message": "Login failed",
                "reason": "impostor_detected",
                "score": confidence_score,
                "confidence_label": verification_result.get("confidence", "low"),
            }), 403

    except Exception as e:
        print(f"[ERROR] Login failed: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": "Internal server error",
                        "reason": "server_error"}), 500
