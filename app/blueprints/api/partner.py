"""
Partner-facing API endpoints (API-key authenticated).

Routes
------
POST /api/partner/enroll  — submit one keystroke sample for a partner user
POST /api/partner/verify  — verify a keystroke sample via per-user ML model

Verification menggunakan pendekatan **machine learning per-user** (RandomForest
atau SVM, dipilih lewat env var ``ML_BACKEND``) yang sama dengan internal login
flow. Pendekatan ini memerlukan minimum 10 sampel enrollment per pengguna
sebelum model dapat dilatih. Setelah enrollment mencapai 10 sampel, training
dijalankan asinkron di background thread; partner cukup retry beberapa detik
kemudian apabila menerima response ``training_started``.
"""

from __future__ import annotations

import traceback
from functools import wraps
from typing import Any, Dict, Optional, Tuple

from flask import current_app, g, jsonify, request

from app import limiter as _limiter
from app.models import User, UsersVector, db
from app.services.api_key_service import APIKeyService

from ._shared import api_bp, get_biometric_service
from .helpers import process_events, save_biometric_sample


# ---------------------------------------------------------------------------
# Konstanta enrollment partner — disesuaikan dengan kebijakan internal app.
# ---------------------------------------------------------------------------
PARTNER_MIN_ENROLLMENT = 10   # minimum sebelum verify boleh dijalankan
PARTNER_TARGET_ENROLLMENT = 10  # target enrollment untuk progress indicator


# ---------------------------------------------------------------------------
# Keystroke processing helpers
# ---------------------------------------------------------------------------

def _process_events_for_verify(events, username):
    """Process events untuk verify dengan relaxed backspace gate.

    Pengguna sering melakukan koreksi saat login, jadi batas backspace
    diperlonggar dibanding enrollment yang menuntut sampel bersih.
    """
    from app.utils.keystroke_processor import KeystrokeProcessor
    proc = KeystrokeProcessor(max_allowed_backspace=10_000)
    return proc.process(events, username=username)


# ---------------------------------------------------------------------------
# User helpers
# ---------------------------------------------------------------------------

def _get_or_create_partner_user(username: str, email: Optional[str] = None):
    """Return User row, creating a placeholder if missing.

    Per-user ML training memerlukan row di tabel ``users`` sebagai FK target.
    Partner users tidak melalui flow auth normal, jadi kita materialize User
    row stub dengan ``password_hash=None``.
    """
    user = db.session.execute(
        db.select(User).where(User.username == username)
    ).scalars().first()
    if user:
        if email and not user.email:
            user.email = email
            db.session.flush()
        return user
    user = User(username=username, email=email, password_hash=None)
    db.session.add(user)
    db.session.flush()
    return user


def _scoped_username(api_key, username: str) -> str:
    """Namespace a partner-supplied username to its API key.

    SECURITY: biometric templates are keyed by ``username`` in a GLOBAL table
    shared with internal app users. Without scoping, two partners (or a partner
    and an internal user) that happen to share a username would read, overwrite,
    or poison each other's templates — and a partner could target an internal
    account (e.g. an admin) by simply sending that username. Prefixing with the
    immutable API-key id isolates each partner into its own namespace and makes
    collision with an internal (plain) username impossible.

    The external API contract is unchanged: requests/responses still use the
    partner's own username; scoping is purely an internal storage detail.
    """
    return f"pk{api_key.id}::{username}"


def _count_enrollment_samples(username: str) -> int:
    """Hitung jumlah sampel enrollment yang tersimpan untuk username."""
    return int(db.session.execute(
        db.select(db.func.count())
        .select_from(UsersVector)
        .where(
            UsersVector.username == username,
            (UsersVector.event_type == "enrollment")
            | (UsersVector.data_type == "enrollment"),
        )
    ).scalar() or 0)


# ---------------------------------------------------------------------------
# Confidence label mapping
# ---------------------------------------------------------------------------

def _confidence_label(score: float, threshold: float) -> str:
    """Map probability score ke label kategorikal untuk JS partner."""
    if threshold and score >= threshold * 1.5:
        return "Exact Match"
    if threshold and score >= threshold * 1.2:
        return "High Confidence"
    if threshold and score >= threshold:
        return "Medium Confidence"
    if threshold and score >= threshold * 0.7:
        return "Low Confidence"
    return "Very Low Confidence"


# ---------------------------------------------------------------------------
# Auth decorator
# ---------------------------------------------------------------------------

def _json_error(message, status_code=400, **extra):
    payload = {"success": False, "message": message}
    payload.update(extra)
    return jsonify(payload), status_code


def require_api_key(view):
    """Validate Bearer API key, rate limit, dan (optional) origin allowlist."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        is_valid, api_key, err = APIKeyService.verify_api_key(auth_header)
        if not is_valid:
            return _json_error(err or "Invalid API key", 401, error_code="UNAUTHORIZED")

        allowed, _remaining, rate_err = APIKeyService.check_rate_limit(api_key)
        if not allowed:
            return _json_error(rate_err, 429, error_code="RATE_LIMITED")

        origin = request.headers.get("Origin")
        if origin and not APIKeyService.check_origin_allowed(api_key, origin):
            return _json_error("Origin not allowed for this API key", 403,
                               error_code="ORIGIN_NOT_ALLOWED")

        g.api_key = api_key
        try:
            api_key.update_last_used()
        except Exception:
            db.session.rollback()
        return view(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# Payload helpers
# ---------------------------------------------------------------------------

def _extract_partner_payload() -> Tuple[Dict[str, Any], str, Any, Optional[str]]:
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    events = data.get("events")
    email = data.get("email")
    if isinstance(email, str):
        email = email.strip() or None
    else:
        email = None
    return data, username, events, email


def _client_ip() -> str:
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.remote_addr or ""


def _maybe_schedule_training(username: str, sample_count: int) -> None:
    """Trigger background ML training saat sampel mencapai minimum.

    Training idempotent via ``_training_in_progress`` lock, jadi aman dipanggil
    setiap kali enroll lewat batas minimum.
    """
    if sample_count < PARTNER_MIN_ENROLLMENT:
        return
    try:
        backend_name = str(current_app.config.get("ML_BACKEND", "rf") or "rf").strip().lower()
        backend_name = "svm" if backend_name == "svm" else "rf"
        if backend_name == "svm":
            from app.services.svm_model_service import (
                schedule_background_training as schedule,
            )
        else:
            from app.services.ml_model_service import (
                schedule_background_training as schedule,
            )
        app = current_app._get_current_object()
        # force=True supaya model di-refresh dengan sampel terbaru tiap enroll
        schedule(app, username, force=True)
    except Exception as exc:
        current_app.logger.warning(f"[partner] auto-train skipped: {exc}")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@api_bp.route("/partner/enroll", methods=["POST"])
@_limiter.limit("60 per minute")
@require_api_key
def partner_enroll():
    """Save one keystroke sample untuk partner-supplied username."""
    api_key = g.api_key
    log_entry = None
    try:
        _data, username, events, email = _extract_partner_payload()
        if not username or not events:
            return _json_error("username and events are required", 400,
                               error_code="MISSING_FIELDS")
        if len(username) > 64:
            return _json_error("username too long (max 64)", 400,
                               error_code="INVALID_USERNAME")

        # Scope all biometric storage to this API key (tenant isolation).
        scoped = _scoped_username(api_key, username)

        log_entry = APIKeyService.log_enrollment(
            api_key_id=api_key.id,
            username=username,
            email=email,
            samples_count=len(events) if isinstance(events, list) else 0,
            client_ip=_client_ip(),
            user_agent=request.headers.get("User-Agent"),
            status="processing",
        )

        result = process_events(events, scoped)
        if result.get("status") != "success":
            msg = result.get("msg", "Failed to process keystroke events")
            log_entry.mark_failed(msg)
            return _json_error(msg, 400, error_code="INVALID_KEYSTROKE_DATA")

        features = result["features"]
        features["username"] = scoped
        features["event_type"] = "enrollment"

        partner_user = _get_or_create_partner_user(scoped, email)

        _, save_error = save_biometric_sample(
            username=scoped,
            user_id=partner_user.id,
            features=features,
            event_type="enrollment",
        )
        if save_error:
            log_entry.mark_failed("Database error saving sample")
            return save_error

        db.session.commit()

        new_count = _count_enrollment_samples(scoped)
        enrollment_id = f"enr_{api_key.id}_{log_entry.id}"

        log_entry.user_id = partner_user.id
        log_entry.mark_success(enrollment_id=enrollment_id)

        # Trigger background training otomatis pada setiap enroll setelah
        # minimum tercapai, supaya model siap saat user verify.
        _maybe_schedule_training(scoped, new_count)

        try:
            api_key.total_enrollments = int(api_key.total_enrollments or 0) + 1
            db.session.commit()
        except Exception:
            db.session.rollback()

        return jsonify({
            "success": True,
            "message": f"Sample {new_count}/{PARTNER_TARGET_ENROLLMENT} saved",
            "enrollment_id": enrollment_id,
            "username": username,
            "api_key_prefix": api_key.key_prefix,
            "progress": {
                "current": new_count,
                "target": PARTNER_TARGET_ENROLLMENT,
                "complete": new_count >= PARTNER_TARGET_ENROLLMENT,
            },
            "templates_count": new_count,
            "enrollment_count": new_count,
            "required_templates": PARTNER_TARGET_ENROLLMENT,
            "min_templates": PARTNER_MIN_ENROLLMENT,
            "remaining_quota": api_key.get_remaining_quota(),
        }), 201

    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f"[partner_enroll] {exc}")
        traceback.print_exc()
        if log_entry is not None:
            try:
                log_entry.mark_failed(str(exc))
            except Exception:
                db.session.rollback()
        return _json_error("Internal server error", 500, error_code="SERVER_ERROR")


@api_bp.route("/partner/verify", methods=["POST"])
@_limiter.limit("120 per minute")
@require_api_key
def partner_verify():
    """Verify keystroke sample via per-user ML model (RandomForest/SVM)."""
    api_key = g.api_key
    try:
        _data, username, events, _email = _extract_partner_payload()
        if not username or not events:
            return _json_error("username and events are required", 400,
                               error_code="MISSING_FIELDS")
        if len(username) > 64:
            return _json_error("username too long (max 64)", 400,
                               error_code="INVALID_USERNAME")

        # Scope all biometric lookups to this API key (tenant isolation).
        scoped = _scoped_username(api_key, username)

        existing_user = db.session.execute(
            db.select(User).where(User.username == scoped)
        ).scalars().first()
        user_id = existing_user.id if existing_user else None

        # Cek apakah enrollment sudah mencapai minimum sebelum melanjutkan
        # ke ML inference. Memberikan error message yang lebih jelas dibanding
        # mengandalkan training_started loop.
        current_count = _count_enrollment_samples(scoped)
        if current_count < PARTNER_MIN_ENROLLMENT:
            msg = f"Insufficient enrollment samples ({current_count}/{PARTNER_MIN_ENROLLMENT})"
            APIKeyService.log_verification(
                api_key_id=api_key.id, user_id=user_id, username=username,
                verified=False, confidence_score=0.0, error_message=msg,
                client_ip=_client_ip(),
                user_agent=request.headers.get("User-Agent"),
            )
            return _json_error(
                msg, 404,
                error_code="INSUFFICIENT_ENROLLMENT",
                progress={"current": current_count, "target": PARTNER_MIN_ENROLLMENT},
            )

        # Ensure User row exists supaya training berhasil (FK target).
        if not existing_user:
            _get_or_create_partner_user(scoped)
            db.session.commit()

        result = _process_events_for_verify(events, scoped)
        if result.get("status") != "success":
            msg = result.get("msg", "Failed to process keystroke events")
            APIKeyService.log_verification(
                api_key_id=api_key.id, user_id=user_id, username=username,
                verified=False, confidence_score=0.0, error_message=msg,
                client_ip=_client_ip(),
                user_agent=request.headers.get("User-Agent"),
            )
            return _json_error(msg, 400, error_code="INVALID_KEYSTROKE_DATA")

        features = result["features"]

        # ML verification via BiometricService — sama dengan internal login.
        bio = get_biometric_service()
        verification = bio.verify_keystroke_sample(scoped, features)

        if not verification.get("success"):
            reason = verification.get("reason", "verification_error")
            message = verification.get("message", "Verification error")
            APIKeyService.log_verification(
                api_key_id=api_key.id, user_id=user_id, username=username,
                verified=False, confidence_score=0.0, error_message=message,
                client_ip=_client_ip(),
                user_agent=request.headers.get("User-Agent"),
            )
            # 202 untuk training in progress (klien retry), 400 untuk error riil
            http_status = 202 if reason in ("training_started", "training_in_progress") else 400
            return jsonify({
                "success": False,
                "verified": False,
                "decision": "impostor",
                "message": message,
                "reason": reason,
                "confidence_score": 0.0,
                "confidence_label": "Unavailable",
                "method": verification.get("method"),
            }), http_status

        verified = bool(verification.get("verified"))
        score = float(verification.get("score", 0.0))
        threshold = float(verification.get("threshold") or 0.0)
        decision = "genuine" if verified else "impostor"
        confidence_label = _confidence_label(score, threshold)

        current_app.logger.info(
            f"[partner_verify ML] {username} score={score:.4f} thr={threshold:.4f} "
            f"verified={verified} method={verification.get('method')}"
        )

        # Persist verification sample untuk audit / drift tracking
        save_biometric_sample(
            username=scoped,
            user_id=user_id,
            features=features,
            event_type="login",
            data_type="verification",
            is_successful=verified,
        )
        db.session.commit()

        verification_log = APIKeyService.log_verification(
            api_key_id=api_key.id, user_id=user_id, username=username,
            verified=verified, confidence_score=score,
            error_message=None if verified else "Score below threshold",
            client_ip=_client_ip(),
            user_agent=request.headers.get("User-Agent"),
        )

        try:
            api_key.total_verifications = int(api_key.total_verifications or 0) + 1
            db.session.commit()
        except Exception:
            db.session.rollback()

        return jsonify({
            "success": True,
            "verified": verified,
            "decision": decision,
            "username": username,
            "confidence_score": score,
            "confidence_label": confidence_label,
            "score": score,
            "threshold": threshold,
            "confidence": confidence_label,
            "templates_used": current_count,
            "verification_id": getattr(verification_log, "id", None),
            "api_key_prefix": api_key.key_prefix,
            "remaining_quota": api_key.get_remaining_quota(),
            "method": verification.get("method"),
            "message": "Verified" if verified else "Not verified",
        }), 200

    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f"[partner_verify] {exc}")
        traceback.print_exc()
        return _json_error("Internal server error", 500, error_code="SERVER_ERROR")
