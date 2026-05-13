"""
Partner-facing API endpoints (API-key authenticated).

Routes
------
POST /api/partner/enroll  — submit one keystroke sample for a partner user
POST /api/partner/verify  — verify a keystroke sample against stored templates

Verification uses **template-distance comparison** (euclidean + cosine +
statistical), not per-user ML training. Rationale: per-user SVM/RF with 5-30
enrollment samples degenerates into constant outputs (see memory:
lesson_biometric_architecture). Template distance discriminates cleanly at
small sample counts, has no training step, and returns sub-second.
"""

from __future__ import annotations

import json
import statistics as _stats
import traceback
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from flask import current_app, g, jsonify, request

from app import limiter as _limiter
from app.models import User, UsersVector, db
from app.services.api_key_service import APIKeyService

from ._shared import api_bp
from .helpers import save_biometric_sample


# ---------------------------------------------------------------------------
# Confidence thresholds (mirror habib_api/biometric.py constants)
# ---------------------------------------------------------------------------
EXACT_MATCH_THRESHOLD = 0.95
HIGH_CONFIDENCE_THRESHOLD = 0.85
MEDIUM_CONFIDENCE_THRESHOLD = 0.70
LOW_CONFIDENCE_THRESHOLD = 0.55
MIN_SAMPLES_FOR_VERIFICATION = 3


# ---------------------------------------------------------------------------
# Keystroke processing helpers
# ---------------------------------------------------------------------------

def _process_events(events, username, *, lenient_backspace: bool = False):
    """Process raw events into feature vectors.

    ``lenient_backspace`` lifts the 4-backspace gate that's appropriate for
    enrollment but too strict for live verify (users fat-finger).
    """
    from app.utils.keystroke_processor import KeystrokeProcessor
    proc = KeystrokeProcessor(max_allowed_backspace=10_000 if lenient_backspace else 4)
    return proc.process(events, username=username)


def _safe_parse_vector(raw_value) -> List[float]:
    """Parse a stored vector (JSON string or list) into a list of floats."""
    if raw_value is None:
        return []
    if isinstance(raw_value, list):
        try:
            return [float(x) for x in raw_value]
        except (TypeError, ValueError):
            return []
    if isinstance(raw_value, str):
        try:
            parsed = json.loads(raw_value)
            if isinstance(parsed, list):
                return [float(x) for x in parsed]
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return []


# ---------------------------------------------------------------------------
# Template-distance scoring (ported from habib_api/biometric.py)
# ---------------------------------------------------------------------------

def _euclidean_distance(a: List[float], b: List[float]) -> float:
    return float(np.linalg.norm(np.asarray(a, dtype=float) - np.asarray(b, dtype=float)))


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    va = np.asarray(a, dtype=float)
    vb = np.asarray(b, dtype=float)
    na = float(np.linalg.norm(va))
    nb = float(np.linalg.norm(vb))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def _statistical_similarity(sample_h: List[float], templates: List[Dict[str, Any]]) -> float:
    """Per-position absolute-diff score on H_vector, scaled to [0,1]."""
    template_rows: List[List[float]] = []
    for t in templates:
        hv = t.get("H_vector") or []
        try:
            template_rows.append([float(x) for x in hv])
        except (TypeError, ValueError):
            continue
    if not sample_h or not template_rows:
        return 0.0
    min_len = min(len(sample_h), min(len(r) for r in template_rows))
    if min_len == 0:
        return 0.0
    sample_trimmed = sample_h[:min_len]
    template_trimmed = [r[:min_len] for r in template_rows]
    template_means = [_stats.mean(col) for col in zip(*template_trimmed)]
    diffs = [abs(a - b) for a, b in zip(sample_trimmed, template_means)]
    mean_diff = _stats.mean(diffs)
    return float(1.0 / (1.0 + (mean_diff * 2.0)))


def _confidence_label(score: float) -> str:
    if score >= EXACT_MATCH_THRESHOLD:
        return "Exact Match"
    if score >= HIGH_CONFIDENCE_THRESHOLD:
        return "High Confidence"
    if score >= MEDIUM_CONFIDENCE_THRESHOLD:
        return "Medium Confidence"
    if score >= LOW_CONFIDENCE_THRESHOLD:
        return "Low Confidence"
    return "Very Low Confidence"


def _score_against_templates(
    login_features: Dict[str, Any],
    templates: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Score a login sample against stored enrollment templates.

    Returns dict with: decision, confidence_score, confidence_label, plus
    component scores. Same shape habib_api used for partner verify.
    """
    login_H = login_features.get("H_vector") or []
    login_DD = login_features.get("DD_vector") or []

    if not login_H or not login_DD:
        return {
            "decision": "impostor",
            "confidence_score": 0.0,
            "confidence_label": _confidence_label(0.0),
            "error": "missing required vectors",
            "templates_compared": 0,
        }

    eu_scores: List[float] = []
    cos_scores: List[float] = []

    for t in templates:
        tH = t.get("H_vector") or []
        tDD = t.get("DD_vector") or []
        if len(tH) != len(login_H) or len(tDD) != len(login_DD):
            continue
        eu = (
            1.0 / (1.0 + _euclidean_distance(login_H, tH))
            + 1.0 / (1.0 + _euclidean_distance(login_DD, tDD))
        ) / 2.0
        eu_scores.append(eu)

        cos = (
            ((_cosine_similarity(login_H, tH) + 1.0) / 2.0)
            + ((_cosine_similarity(login_DD, tDD) + 1.0) / 2.0)
        ) / 2.0
        cos_scores.append(cos)

    if not eu_scores and not cos_scores:
        return {
            "decision": "impostor",
            "confidence_score": 0.0,
            "confidence_label": _confidence_label(0.0),
            "error": "no valid template comparisons (length mismatch)",
            "templates_compared": 0,
        }

    eu_score = float(np.mean(eu_scores)) if eu_scores else 0.0
    cos_score = float(np.mean(cos_scores)) if cos_scores else 0.0
    stat_score = _statistical_similarity(login_H, templates)

    base = 0.5 * eu_score + 0.3 * cos_score + 0.2 * stat_score
    base = float(max(0.0, min(1.0, base)))
    # Calibrate by emphasizing statistical alignment (reduces false accepts)
    calibrated = float(max(0.0, min(1.0, base * stat_score)))

    # Decision threshold is configurable via PARTNER_DECISION_THRESHOLD env var.
    # Default = MEDIUM_CONFIDENCE_THRESHOLD (0.70). Set to 0.90 for strict mode.
    decision_threshold = float(
        current_app.config.get("PARTNER_DECISION_THRESHOLD", MEDIUM_CONFIDENCE_THRESHOLD)
    )
    decision_threshold = max(0.0, min(1.0, decision_threshold))
    decision = "genuine" if calibrated >= decision_threshold else "impostor"

    return {
        "decision": decision,
        "confidence_score": round(calibrated, 4),
        "confidence_label": _confidence_label(calibrated),
        "euclidean_score": round(eu_score, 4),
        "cosine_score": round(cos_score, 4),
        "statistical_score": round(stat_score, 4),
        "templates_compared": len(eu_scores),
    }


# ---------------------------------------------------------------------------
# Template loader
# ---------------------------------------------------------------------------

def _load_partner_enrollment_templates(username: str) -> List[Dict[str, Any]]:
    """Load enrollment templates (parsed vectors) for *username*."""
    rows = db.session.execute(
        db.select(UsersVector)
        .where(
            UsersVector.username == username,
            (UsersVector.event_type == "enrollment")
            | (UsersVector.data_type == "enrollment"),
        )
        .order_by(UsersVector.id.desc())
    ).scalars().all()

    templates: List[Dict[str, Any]] = []
    for row in rows:
        h_vec = _safe_parse_vector(getattr(row, "H_vector", None))
        dd_vec = _safe_parse_vector(getattr(row, "DD_vector", None))
        if not h_vec or not dd_vec:
            continue
        templates.append({
            "H_vector": h_vec,
            "DD_vector": dd_vec,
            "UD_vector": _safe_parse_vector(getattr(row, "UD_vector", None)),
        })
    return templates


# ---------------------------------------------------------------------------
# User helpers
# ---------------------------------------------------------------------------

def _get_or_create_partner_user(username: str, email: Optional[str] = None):
    """Return User row, creating a placeholder if missing.

    Keeps FK integrity for the user_id column on UsersVector. Password is
    NULL — partner users don't authenticate via password here.
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


def _count_enrollment_samples(username: str) -> int:
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

        result = _process_events(events, username, lenient_backspace=False)
        if result.get("status") != "success":
            msg = result.get("msg", "Failed to process keystroke events")
            log_entry.mark_failed(msg)
            return _json_error(msg, 400, error_code="INVALID_KEYSTROKE_DATA")

        features = result["features"]
        features["username"] = username
        features["event_type"] = "enrollment"

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

        new_count = _count_enrollment_samples(username)
        target = 5  # template-distance is reliable from 5 samples; no need for 30
        enrollment_id = f"enr_{api_key.id}_{log_entry.id}"

        log_entry.user_id = partner_user.id
        log_entry.mark_success(enrollment_id=enrollment_id)

        try:
            api_key.total_enrollments = int(api_key.total_enrollments or 0) + 1
            db.session.commit()
        except Exception:
            db.session.rollback()

        return jsonify({
            "success": True,
            "message": f"Sample {new_count}/{target} saved",
            "enrollment_id": enrollment_id,
            "username": username,
            "api_key_prefix": api_key.key_prefix,
            "progress": {
                "current": new_count,
                "target": target,
                "complete": new_count >= target,
            },
            "templates_count": new_count,
            "enrollment_count": new_count,
            "required_templates": target,
            "min_templates": target,
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
    """Verify a keystroke sample against stored templates using template distance."""
    api_key = g.api_key
    try:
        _data, username, events, _email = _extract_partner_payload()
        if not username or not events:
            return _json_error("username and events are required", 400,
                               error_code="MISSING_FIELDS")

        existing_user = db.session.execute(
            db.select(User).where(User.username == username)
        ).scalars().first()
        user_id = existing_user.id if existing_user else None

        templates = _load_partner_enrollment_templates(username)
        if len(templates) < MIN_SAMPLES_FOR_VERIFICATION:
            msg = f"Insufficient enrollment samples ({len(templates)}/{MIN_SAMPLES_FOR_VERIFICATION})"
            APIKeyService.log_verification(
                api_key_id=api_key.id, user_id=user_id, username=username,
                verified=False, confidence_score=0.0, error_message=msg,
                client_ip=_client_ip(),
                user_agent=request.headers.get("User-Agent"),
            )
            return _json_error(
                msg, 404,
                error_code="INSUFFICIENT_ENROLLMENT",
                progress={"current": len(templates), "target": MIN_SAMPLES_FOR_VERIFICATION},
            )

        result = _process_events(events, username, lenient_backspace=True)
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
        scored = _score_against_templates(features, templates)

        decision = scored["decision"]
        verified = decision == "genuine"
        confidence_score = scored["confidence_score"]
        confidence_label = scored["confidence_label"]

        current_app.logger.info(
            f"[partner_verify] {username} templates={scored.get('templates_compared')} "
            f"eu={scored.get('euclidean_score')} cos={scored.get('cosine_score')} "
            f"stat={scored.get('statistical_score')} → confidence={confidence_score} "
            f"label={confidence_label} decision={decision}"
        )

        # Persist verification sample for audit / drift tracking
        save_biometric_sample(
            username=username,
            user_id=user_id,
            features=features,
            event_type="login",
            data_type="verification",
            is_successful=verified,
        )
        db.session.commit()

        verification_log = APIKeyService.log_verification(
            api_key_id=api_key.id, user_id=user_id, username=username,
            verified=verified, confidence_score=confidence_score,
            error_message=None if verified else scored.get("error", "Score below threshold"),
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
            "confidence_score": confidence_score,
            "confidence_label": confidence_label,
            "score": confidence_score,
            "confidence": confidence_label,
            "templates_used": scored.get("templates_compared", len(templates)),
            "verification_id": getattr(verification_log, "id", None),
            "api_key_prefix": api_key.key_prefix,
            "remaining_quota": api_key.get_remaining_quota(),
            "method": "template_distance",
            "message": "Verified" if verified else "Not verified",
        }), 200

    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f"[partner_verify] {exc}")
        traceback.print_exc()
        return _json_error("Internal server error", 500, error_code="SERVER_ERROR")
