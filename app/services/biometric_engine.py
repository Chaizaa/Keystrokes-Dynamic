"""Biometric engine glue used by API routes.

This module adapts incoming API payloads to the application's canonical
biometric storage (EnrollmentVector / KeystrokeVector) and uses the
`BiometricService` to run verification.
"""
import json
from typing import Tuple

from app.models import db, EnrollmentVector, KeystrokeVector, User
from app.services.biometric import BiometricService


def _create_enrollment_row(user_id: int, sample) -> bool:
    """Persist a single enrollment sample to `enrollment_vectors` if possible.

    Accepts either a dict with vector keys (H_vector, DD_vector, etc.) or
    an arbitrary object which will be stored in `raw_events`.
    Returns True on success.
    """
    try:
        # Resolve username for denormalized column
        user = db.session.get(User, user_id)
        username = user.username if user else None
        ev = EnrollmentVector(user_id=user_id, username=username or "", event_type="enrollment")
        # If sample contains vector fields, set them
        if isinstance(sample, dict):
            if "H_vector" in sample:
                ev.H_vector = json.dumps(sample.get("H_vector") or [])
            if "DD_vector" in sample:
                ev.DD_vector = json.dumps(sample.get("DD_vector") or [])
            if "UD_vector" in sample:
                ev.UD_vector = json.dumps(sample.get("UD_vector") or [])
            if "UU_vector" in sample:
                ev.UU_vector = json.dumps(sample.get("UU_vector") or [])
            if "DU_vector" in sample:
                ev.DU_vector = json.dumps(sample.get("DU_vector") or [])
            # Keep raw events for auditing/compatibility
            ev.raw_events = json.dumps(sample)
        else:
            ev.raw_events = json.dumps(sample)

        db.session.add(ev)
        # Do not commit here; caller will commit after batch insert
        return True
    except Exception:
        return False


def enroll_user(user_id: int, keystroke_data) -> int:
    """Persist provided keystroke samples for `user_id`.

    keystroke_data is expected to be a list of samples. Each sample may be
    a dict containing vector fields or an arbitrary JSON-serializable object.

    Returns the number of samples persisted.
    """
    if not isinstance(keystroke_data, list):
        return 0
    processed = 0
    for s in keystroke_data:
        ok = _create_enrollment_row(user_id, s)
        if ok:
            processed += 1
    if processed:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return 0
    return processed


def verify_user(user_id: int, keystroke_data) -> Tuple[bool, float]:
    """Verify provided keystroke sample against user's enrollment templates.

    Returns (verified, score). Uses `BiometricService.verify_keystroke_sample`.
    """
    bio = BiometricService()
    # Build a login_sample expected by the service
    sample = {}
    if isinstance(keystroke_data, dict):
        sample = keystroke_data
    elif isinstance(keystroke_data, list):
        # If provided as a list of numbers, store as H_vector
        sample = {"H_vector": keystroke_data, "DD_vector": keystroke_data}
    else:
        sample = {}

    # Determine username
    user = db.session.get(User, user_id)
    username = user.username if user else None
    if username:
        result = bio.verify_keystroke_sample(username, sample)
    else:
        result = bio.verify_keystroke_sample(sample, [])

    # Normalize result to (verified, score)
    if isinstance(result, dict):
        # Legacy structure
        verified = bool(result.get("verified") or result.get("success") or False)
        score = float(result.get("score") or result.get("confidence_score") or 0.0)
        return verified, score
    # Fallback
    return False, 0.0
