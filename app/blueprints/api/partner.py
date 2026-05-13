"""
Partner-facing API endpoints (API-key authenticated).

These routes are consumed by external sites embedding
``static/js/partner_keystroke_recorder.js``. Authentication is via the
``Authorization: Bearer sk_live_...`` header, validated against the
``api_keys`` table by :class:`APIKeyService`.

Routes
------
POST /api/partner/enroll  — submit one keystroke sample for a partner user
POST /api/partner/verify  — verify a keystroke sample against the user's model
"""

from __future__ import annotations

import traceback
from functools import wraps

from flask import current_app, g, jsonify, request

from app import limiter as _limiter
from app.models import User, UsersVector, db
from app.services.api_key_service import APIKeyService

from ._shared import api_bp, get_biometric_service
from .helpers import assess_quality, process_events, save_biometric_sample


def _process_events_for_verify(events, username):
    """Process events with relaxed quality gates (no backspace cap)."""
    from app.utils.keystroke_processor import KeystrokeProcessor
    return KeystrokeProcessor(max_allowed_backspace=10_000).process(events, username=username)


def _permissive_threshold(strict_threshold, enrollment_count):
    """Return an effective threshold relaxed for low-sample users.

    Combines two relaxations and picks the more permissive (lower) one:
      - Multiplicative factor: ``threshold * factor``
      - Absolute tolerance band: ``threshold - tolerance``

    The absolute tolerance ensures a small numeric gap (e.g. 0.04 below the
    learned threshold) is never enough to block a legitimate user, regardless
    of the threshold's magnitude.

    Tunable via Flask config:
      - PARTNER_PERMISSIVE_ENABLED    (default True)
      - PARTNER_PERMISSIVE_FACTOR     (default 0.3; 1.0 = no relaxation)
      - PARTNER_PERMISSIVE_TOLERANCE  (default 0.08; absolute band)
      - PARTNER_PERMISSIVE_BELOW      (default 15; sample count cutoff)
    """
    cfg = current_app.config
    if not cfg.get("PARTNER_PERMISSIVE_ENABLED", True):
        return strict_threshold, False
    cutoff = int(cfg.get("PARTNER_PERMISSIVE_BELOW", 15))
    if enrollment_count >= cutoff or strict_threshold is None:
        return strict_threshold, False
    factor = float(cfg.get("PARTNER_PERMISSIVE_FACTOR", 0.3))
    factor = max(0.05, min(1.0, factor))
    tolerance = float(cfg.get("PARTNER_PERMISSIVE_TOLERANCE", 0.08))
    tolerance = max(0.0, tolerance)

    by_factor = float(strict_threshold) * factor
    by_tolerance = float(strict_threshold) - tolerance
    effective = max(0.0, min(by_factor, by_tolerance))
    return effective, True


def _get_or_create_partner_user(username, email=None):
    """Return a User row for *username*, creating a placeholder if missing.

    Per-user ML training requires a row in ``users`` (FK target). Partner-supplied
    usernames are not part of the regular auth flow, so we materialize a
    password-less stub User so that training can proceed.

    Also backfills ``user_id`` on any orphan UsersVector rows for this username
    so previously-enrolled partner samples become attributable.
    """
    user = db.session.execute(
        db.select(User).where(User.username == username)
    ).scalars().first()
    created = False
    if not user:
        user = User(username=username, email=email, password_hash=None)
        db.session.add(user)
        db.session.flush()
        created = True
    elif email and not user.email:
        user.email = email
        db.session.flush()

    # Heal any orphan vector rows so ML training has a consistent foreign key.
    db.session.execute(
        db.update(UsersVector)
        .where(UsersVector.username == username, UsersVector.user_id.is_(None))
        .values(user_id=user.id)
    )
    if created:
        current_app.logger.info(f"[partner] created placeholder User for {username}")
    return user


# ---------------------------------------------------------------------------
# Auth decorator
# ---------------------------------------------------------------------------

def _json_error(message, status_code=400, **extra):
    payload = {"success": False, "message": message}
    payload.update(extra)
    return jsonify(payload), status_code


def require_api_key(view):
    """Validate Bearer API key, rate limit, and (optional) origin allowlist."""

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
# Helpers
# ---------------------------------------------------------------------------

def _recommended_samples() -> int:
    bio = get_biometric_service()
    getter = getattr(bio, "get_recommended_samples", None)
    if callable(getter):
        try:
            return int(getter())
        except Exception:
            pass
    return int(getattr(bio, "RECOMMENDED_SAMPLES", 30))


def _extract_partner_payload():
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
    """Kick off background ML training as soon as we have the minimum samples.

    Triggers on every enroll past the minimum (training is cheap with the
    pruned grid and idempotent via ``_training_in_progress``). This way, the
    model is ready by the time the user lands on the verify call and we never
    have to sync-train inside the verify request.
    """
    bio = get_biometric_service()
    min_samples = int(getattr(bio, "get_minimum_samples_for_verification", lambda: 5)())
    if sample_count < min_samples:
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
        # force=True so each new enroll sample refreshes the model with the
        # latest data; quick grid keeps this cheap.
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
    """Save one keystroke sample for a partner-supplied username."""
    api_key = g.api_key
    log_entry = None
    try:
        _data, username, events, email = _extract_partner_payload()
        if not username or not events:
            return _json_error("username and events are required", 400,
                               error_code="MISSING_FIELDS")

        log_entry = APIKeyService.log_enrollment(
            api_key_id=api_key.id,
            username=username,
            email=email,
            samples_count=len(events) if isinstance(events, list) else 0,
            client_ip=_client_ip(),
            user_agent=request.headers.get("User-Agent"),
            status="processing",
        )

        result = process_events(events, username)
        if result.get("status") != "success":
            msg = result.get("msg", "Failed to process keystroke events")
            log_entry.mark_failed(msg)
            return _json_error(msg, 400, error_code="INVALID_EVENTS")

        features = result["features"]
        features["username"] = username
        features["event_type"] = "enrollment"

        quality = assess_quality(features)
        features["quality_label"] = quality.get("quality_label")
        features["quality_score"] = quality.get("quality_score")

        partner_user = _get_or_create_partner_user(username, email)

        _, save_error = save_biometric_sample(
            username=username,
            user_id=partner_user.id,
            features=features,
            event_type="enrollment",
        )
        if save_error:
            log_entry.mark_failed("Database error saving sample")
            return save_error

        db.session.commit()

        status = get_biometric_service().get_enrollment_status(username)
        target = _recommended_samples()
        new_count = int(status.get("count", 0))

        _maybe_schedule_training(username, new_count)

        log_entry.mark_success(enrollment_id=f"enr_{api_key.id}_{log_entry.id}")

        return jsonify({
            "success": True,
            "message": f"Sample {new_count}/{target} saved",
            "progress": {
                "current": new_count,
                "target": target,
                "complete": bool(status.get("ready_for_login")),
            },
            # Aliases for partner JS clients that read flat field names.
            "templates_count": new_count,
            "enrollment_count": new_count,
            "required_templates": target,
            "min_templates": target,
            "quality": quality,
        }), 200

    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f"[partner_enroll] {exc}")
        traceback.print_exc()
        if log_entry is not None:
            try:
                log_entry.mark_failed(str(exc))
            except Exception:
                db.session.rollback()
        return _json_error("Internal server error", 500, error_code="INTERNAL_ERROR")


@api_bp.route("/partner/verify", methods=["POST"])
@_limiter.limit("120 per minute")
@require_api_key
def partner_verify():
    """Verify a keystroke sample for a partner-supplied username."""
    api_key = g.api_key
    try:
        _data, username, events, _email = _extract_partner_payload()
        if not username or not events:
            return _json_error("username and events are required", 400,
                               error_code="MISSING_FIELDS")

        bio = get_biometric_service()
        status = bio.get_enrollment_status(username)
        min_samples = int(status.get("minimum_samples", 5))
        current_count = int(status.get("count", 0))
        if current_count < min_samples:
            APIKeyService.log_verification(
                api_key_id=api_key.id,
                username=username,
                verified=False,
                confidence_score=None,
                error_message=f"Insufficient enrollment ({current_count}/{min_samples})",
                client_ip=_client_ip(),
                user_agent=request.headers.get("User-Agent"),
            )
            return _json_error(
                f"User not enrolled or enrollment insufficient ({current_count}/{min_samples})",
                404,
                error_code="ENROLLMENT_INSUFFICIENT",
                progress={"current": current_count, "target": min_samples},
            )

        # Heal partner records: ensure User row exists and orphan vectors are
        # linked. Required for per-user ML training to succeed.
        _get_or_create_partner_user(username)
        db.session.commit()

        # First-time verify: train synchronously so the partner gets a real
        # answer rather than polling on 202. Training is fast (~2-5s) for
        # typical sample counts and only happens once per user.
        backend_service = bio._backend_bundle()["service"]
        if backend_service.get_model_row(username) is None:
            # Count *usable* genuine rows (all feature columns populated) before
            # invoking training, so we can return a precise error instead of
            # letting sklearn raise a cryptic stratification message.
            from app.services.base_model_service import FEATURE_COLUMNS as _FC
            usable_q = db.select(UsersVector).where(
                UsersVector.username == username,
                (UsersVector.event_type == "enrollment")
                | (UsersVector.data_type == "enrollment"),
            )
            usable_rows = db.session.execute(usable_q).scalars().all()
            usable_count = sum(
                1 for r in usable_rows
                if all(getattr(r, c, None) is not None for c in _FC)
            )
            current_app.logger.info(
                f"[partner_verify] {username}: enrollment_rows={len(usable_rows)} "
                f"usable_for_training={usable_count}"
            )
            # train_test_split with test_size=0.4 then 0.5 needs >= 5 genuine
            # rows for stratified splits to succeed without sklearn errors.
            MIN_USABLE = 5
            if usable_count < MIN_USABLE:
                APIKeyService.log_verification(
                    api_key_id=api_key.id, username=username, verified=False,
                    confidence_score=None,
                    error_message=(
                        f"insufficient_usable_samples ({usable_count}/{MIN_USABLE}) "
                        f"of {len(usable_rows)} total"
                    ),
                    client_ip=_client_ip(),
                    user_agent=request.headers.get("User-Agent"),
                )
                return _json_error(
                    f"Need at least {MIN_USABLE} complete enrollment samples to "
                    f"train (have {usable_count} usable out of {len(usable_rows)}). "
                    "Submit more enrollment samples and try again.",
                    422,
                    error_code="INSUFFICIENT_SAMPLES",
                    reason="insufficient_usable_samples",
                    diagnostics={
                        "usable_for_training": usable_count,
                        "total_enrollment_rows": len(usable_rows),
                        "minimum_needed": MIN_USABLE,
                    },
                )

            train_result = bio.train_user_model(username, force=False)
            if not train_result.get("success"):
                reason = train_result.get("reason", "train_failed")
                message = train_result.get("message", "Model training failed")
                current_app.logger.error(
                    f"[partner_verify] sync train failed for {username}: "
                    f"reason={reason} message={message}"
                )
                APIKeyService.log_verification(
                    api_key_id=api_key.id,
                    username=username,
                    verified=False,
                    confidence_score=None,
                    error_message=f"train_failed: {reason} — {message}",
                    client_ip=_client_ip(),
                    user_agent=request.headers.get("User-Agent"),
                )
                return _json_error(message, 503,
                                   error_code="TRAIN_FAILED", reason=reason)

        # Verify uses relaxed gates: do not block on corrections — the ML model
        # decides whether the keystroke rhythm matches.
        result = _process_events_for_verify(events, username)
        if result.get("status") != "success":
            msg = result.get("msg", "Failed to process keystroke events")
            APIKeyService.log_verification(
                api_key_id=api_key.id,
                username=username,
                verified=False,
                confidence_score=None,
                error_message=msg,
                client_ip=_client_ip(),
                user_agent=request.headers.get("User-Agent"),
            )
            return _json_error(msg, 400, error_code="INVALID_EVENTS")

        features = result["features"]

        # ---- DEBUG: prove features actually vary across requests ----
        try:
            import hashlib as _hl
            from app.services.base_model_service import FEATURE_COLUMNS as _FC
            feat_vals = [features.get(c) for c in _FC]
            feat_repr = ",".join(
                f"{v:.4f}" if isinstance(v, (int, float)) and v is not None else "None"
                for v in feat_vals
            )
            feat_hash = _hl.md5(feat_repr.encode()).hexdigest()[:8]
            current_app.logger.info(
                f"[partner_verify DEBUG] {username} "
                f"events={len(events)} duration={features.get('total_duration')} "
                f"speed={features.get('typing_speed')} "
                f"H_mean={features.get('H_mean')} DD_mean={features.get('DD_mean')} "
                f"UD_mean={features.get('UD_mean')} feat_hash={feat_hash}"
            )
        except Exception as _dbg_exc:
            current_app.logger.warning(f"[partner_verify DEBUG] failed: {_dbg_exc}")
        # ---- end debug ----

        verification = bio.verify_keystroke_sample(username, features)

        if not verification.get("success"):
            reason = verification.get("reason", "verification_error")
            message = verification.get("message", "Verification error")
            APIKeyService.log_verification(
                api_key_id=api_key.id,
                username=username,
                verified=False,
                confidence_score=None,
                error_message=message,
                client_ip=_client_ip(),
                user_agent=request.headers.get("User-Agent"),
            )
            http_status = 202 if reason in ("training_started", "training_in_progress") else 400
            return jsonify({
                "success": False,
                "verified": False,
                "message": message,
                "reason": reason,
            }), http_status

        score = float(verification.get("score", 0.0))
        strict_threshold = verification.get("threshold")
        strict_verified = bool(verification.get("verified"))

        # Apply permissive threshold for low-sample users. Re-derives the
        # verified flag using the relaxed threshold when active.
        effective_threshold, permissive_active = _permissive_threshold(
            strict_threshold, current_count,
        )
        if permissive_active and not strict_verified and strict_threshold is not None:
            verified = score >= effective_threshold
            decision_source = "permissive"
        else:
            verified = strict_verified
            decision_source = "strict"

        # Single, consistent partner-facing message/confidence regardless of
        # which decision path produced the result. Partner integrations
        # commonly key off these fields, so they must not leak "failed" or
        # "permissive" wording when the final decision is verified=true.
        message = "Verified" if verified else "Not verified"
        if verified:
            partner_confidence = "high" if decision_source == "strict" else "medium"
        else:
            partner_confidence = "low"

        if permissive_active:
            current_app.logger.info(
                f"[partner_verify] {username} permissive: "
                f"score={score:.4f} strict_thr={strict_threshold} "
                f"effective_thr={effective_threshold:.4f} "
                f"enrolled={current_count} verified={verified} "
                f"decision_source={decision_source}"
            )

        # Persist verification sample for audit / drift tracking
        existing_user = db.session.execute(
            db.select(User).where(User.username == username)
        ).scalars().first()
        save_biometric_sample(
            username=username,
            user_id=existing_user.id if existing_user else None,
            features=features,
            event_type="login",
            data_type="verification",
            is_successful=verified,
        )
        db.session.commit()

        APIKeyService.log_verification(
            api_key_id=api_key.id,
            username=username,
            verified=verified,
            confidence_score=score,
            error_message=None if verified else "Score below threshold",
            client_ip=_client_ip(),
            user_agent=request.headers.get("User-Agent"),
        )

        # Legacy field names kept for partner JS clients that read
        # ``confidence_score`` / ``confidence_label`` / ``decision``.
        # ``decision`` is the dominant signal: "genuine" when verified=True so
        # the partner's ``decision === "genuine"`` check passes regardless of
        # the raw numeric score (which can be well under 0.5 with small models).
        response = {
            "success": True,
            "verified": verified,
            "score": score,
            "threshold": effective_threshold,
            "confidence": partner_confidence,
            "confidence_label": partner_confidence,
            "confidence_score": 1.0 if verified else score,
            "decision": "genuine" if verified else "impostor",
            "method": verification.get("method"),
            "message": message,
        }
        return jsonify(response), 200

    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f"[partner_verify] {exc}")
        traceback.print_exc()
        return _json_error("Internal server error", 500, error_code="INTERNAL_ERROR")
