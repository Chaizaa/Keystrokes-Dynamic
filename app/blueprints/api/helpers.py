"""Shared helper utilities for API blueprints."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from flask import jsonify

from app.models import AdminAudit, EnrollmentVector, db


def error_response(message: str, reason: str = "error", status_code: int = 400):
    """Standardized error response for API endpoints."""
    return jsonify({
        "success": False,
        "status": "error",
        "message": message,
        "reason": reason
    }), status_code


def log_audit(action: str, user_id: Optional[int], username: str, details: Dict[str, Any] = None):
    """Centrally log an admin/system audit event (does NOT commit)."""
    try:
        AdminAudit.log(
            action=action,
            user_id=user_id,
            username=username,
            details=details or {}
        )
    except Exception as e:
        print(f"[WARN] Failed to log audit: {e}")


def assess_quality(features: Dict[str, Any]) -> Dict[str, Any]:
    """Assess sample quality using the KeystrokeProcessor's heuristic."""
    from app.utils.keystroke_processor import KeystrokeProcessor
    processor = KeystrokeProcessor()
    return processor.assess_quality(features)


def process_events(events: list, username: str) -> Dict[str, Any]:
    """Helper to process web events using the KeystrokeProcessor."""
    if not isinstance(events, list):
        return {"status": "error", "msg": "Invalid payload: events must be a list"}
    if len(events) > 1000:
        return {"status": "error", "msg": "Payload too large: maximum 1000 events allowed"}

    from app.utils.keystroke_processor import KeystrokeProcessor
    processor = KeystrokeProcessor()
    return processor.process(events, username=username)


def save_biometric_sample(
    username: str, 
    user_id: Optional[int], 
    features: Dict[str, Any], 
    password_hash: Optional[str] = None,
    *,
    event_type: str = "enrollment",
    data_type: Optional[str] = None,
    is_successful: Optional[bool] = None,
) -> Tuple[Optional[EnrollmentVector], Optional[Any]]:
    """Centrally persist a biometric sample (enrollment OR verification) to EnrollmentVector.

    Defaults to enrollment behaviour. Pass event_type='login' and data_type='verification'
    for verification samples recorded during the login flow.
    """
    try:
        ev = EnrollmentVector(
            username=username, 
            user_id=user_id, 
            event_type=event_type
        )
        if data_type is not None:
            ev.data_type = data_type
        if is_successful is not None:
            ev.is_successful = is_successful
        ev.timestamp = datetime.now(timezone.utc).isoformat()
        ev.total_duration = features.get("total_duration")
        ev.typing_speed = features.get("typing_speed")

        # Copy raw timing vectors
        for vec_name in ("H", "DD", "UD", "UU", "DU"):
            vec_data = features.get(f"{vec_name}_vector", [])
            setattr(ev, f"{vec_name}_vector", json.dumps(vec_data))

        # Copy stats (mean, std, min, max, cv)
        for prefix in ("H", "DD", "UD", "UU", "DU"):
            for stat in ("mean", "std", "min", "max", "cv"):
                col = f"{prefix}_{stat}"
                if hasattr(ev, col):
                    setattr(ev, col, features.get(col))

        db.session.add(ev)

        # Log to AdminAudit (passive)
        log_audit(
            action=AdminAudit.ACTION_ENROLLED,
            user_id=user_id,
            username=username,
            details={
                "quality_label": features.get("quality_label"),
                "password_strength": features.get("password_strength"),
            }
        )
        # Note: We do NOT commit here. The caller (endpoint) is responsible for the final commit.
        return ev, None

    except Exception as e:
        print(f"[ERROR] save_biometric_sample: {e}")
        db.session.rollback()
        return None, (jsonify({"status": "error", "message": "Database error saving sample"}), 500)
