"""Enrollment and verification routes for the external client API."""

import json
from datetime import datetime, timezone

from flask import g, jsonify, request
from sqlalchemy import and_

from app.models import UsersVector, db
from app.services.biometric_service import BiometricService

from . import api

# One shared BiometricService instance for this blueprint
_biometric = BiometricService()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _scoped_username(client_id: int, user_id: str) -> str:
    """Build the namespaced username key that uniquely identifies a user
    within a specific client's data partition.

    Format: ``client:<client_id>::user:<user_id>``
    """
    return f"client:{client_id}::user:{user_id}"


def _client_user_filter(client_id: int, user_id: str):
    """Return a SQLAlchemy AND-filter that explicitly isolates rows by both
    *client_id* and *user_id*.

    Two conditions are combined:

    * ``username LIKE 'client:<client_id>::%'`` — guarantees records never
      cross client boundaries even if another condition were weakened.
    * ``username = 'client:<client_id>::user:<user_id>'`` — pins the exact
      user within that client partition.
    """
    client_prefix = f"client:{client_id}::%"
    scoped = _scoped_username(client_id, user_id)
    return and_(
        UsersVector.username.like(client_prefix),   # client_id guard
        UsersVector.username == scoped,             # user_id precision
    )


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------

def enroll_keystroke(client_id: int, user_id: str, samples: list) -> dict:
    """Persist one or more keystroke samples for a client-scoped user.

    Args:
        client_id: ID of the authenticated :class:`~app.models.Client`.
        user_id:   Arbitrary user identifier supplied by the client.
        samples:   List of sample dicts, each containing keystroke vectors
                   (``H_vector``, ``DD_vector``, ``UD_vector``, etc.).

    Returns:
        A dict summarising the result, e.g.::

            {"stored": 5, "total_enrollment": 12}
    """
    if not samples or not isinstance(samples, list):
        raise ValueError("samples must be a non-empty list")

    scoped_username = _scoped_username(client_id, user_id)
    timestamp = datetime.now(timezone.utc).isoformat()
    stored = 0

    for sample in samples:
        if not isinstance(sample, dict):
            continue

        vec = UsersVector(
            username=scoped_username,
            data_type="enrollment",
            event_type="enrollment",
            timestamp=timestamp,
        )

        for name in ("H", "DD", "UD", "UU", "DU"):
            raw = sample.get(f"{name}_vector")
            if raw is not None:
                vec.set_vector(name, raw if isinstance(raw, list) else json.loads(raw))

        # Forward any flat stat columns if the caller provides them
        for col in (
            "H_mean", "H_std", "H_min", "H_max", "H_cv",
            "DD_mean", "DD_std", "DD_min", "DD_max", "DD_cv",
            "UD_mean", "UD_std", "UD_min", "UD_max", "UD_cv",
            "UU_mean", "UU_std", "UU_min", "UU_max", "UU_cv",
            "DU_mean", "DU_std", "DU_min", "DU_max", "DU_cv",
            "total_duration", "typing_speed",
        ):
            val = sample.get(col)
            if val is not None:
                setattr(vec, col, float(val))

        db.session.add(vec)
        stored += 1

    db.session.commit()

    # Count uses the same explicit client_id + user_id compound filter
    total = (
        UsersVector.query
        .filter(_client_user_filter(client_id, user_id))
        .filter(UsersVector.data_type == "enrollment")
        .count()
    )

    return {"stored": stored, "total_enrollment": total}


def verify_keystroke(client_id: int, user_id: str, sample: dict) -> dict:
    """Verify a keystroke sample against a client-scoped user's enrolled templates.

    Args:
        client_id: ID of the authenticated :class:`~app.models.Client`.
        user_id:   Arbitrary user identifier supplied by the client.
        sample:    Dict containing keystroke vectors for the verification attempt.

    Returns:
        The result dict from
        :meth:`~app.services.biometric_service.BiometricService.verify_keystroke_sample`,
        e.g.::

            {
                "decision": "genuine",
                "confidence_score": 0.91,
                "confidence_label": "High Confidence",
                ...
            }
    """
    # Explicit client_id + user_id filter — records from other clients are
    # structurally unreachable even if user_id values happen to collide.
    rows = (
        UsersVector.query
        .filter(_client_user_filter(client_id, user_id))
        .filter(UsersVector.data_type == "enrollment")
        .all()
    )

    templates = [
        {
            "H_vector":  row.get_vector("H"),
            "DD_vector": row.get_vector("DD"),
            "UD_vector": row.get_vector("UD"),
            "UU_vector": row.get_vector("UU"),
            "DU_vector": row.get_vector("DU"),
        }
        for row in rows
    ]

    return _biometric.verify_keystroke_sample(sample, templates)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@api.route("/enroll", methods=["POST"])
def enroll():
    """Enroll keystroke samples for a user.

    Request body::

        {
          "user_id": "<string>",
          "samples": [
            {
              "H_vector":  [0.12, 0.10, ...],
              "DD_vector": [0.08, 0.09, ...],
              "UD_vector": [0.05, 0.06, ...]
            },
            ...
          ]
        }

    Response (200)::

        {
          "status": "ok",
          "stored": 5,
          "total_enrollment": 12
        }
    """
    body = request.get_json(silent=True) or {}
    user_id = body.get("user_id")
    samples = body.get("samples")

    if not user_id:
        return jsonify({"error": "Bad Request", "message": "user_id is required."}), 400
    if not samples or not isinstance(samples, list):
        return jsonify({"error": "Bad Request", "message": "samples must be a non-empty list."}), 400

    try:
        result = enroll_keystroke(
            client_id=g.client.id,
            user_id=str(user_id),
            samples=samples,
        )
    except ValueError as exc:
        return jsonify({"error": "Bad Request", "message": str(exc)}), 400
    except Exception as exc:  # pragma: no cover
        return jsonify({"error": "Internal Server Error", "message": str(exc)}), 500

    return jsonify({"status": "ok", **result}), 200


@api.route("/verify", methods=["POST"])
def verify():
    """Verify a keystroke sample against a user's enrolled templates.

    Request body::

        {
          "user_id": "<string>",
          "sample": {
            "H_vector":  [0.12, 0.10, ...],
            "DD_vector": [0.08, 0.09, ...],
            "UD_vector": [0.05, 0.06, ...]
          }
        }

    Response (200)::

        {
          "status": "ok",
          "decision": "genuine",
          "confidence_score": 0.91,
          "confidence_label": "High Confidence",
          ...
        }
    """
    body = request.get_json(silent=True) or {}
    user_id = body.get("user_id")
    sample = body.get("sample")

    if not user_id:
        return jsonify({"error": "Bad Request", "message": "user_id is required."}), 400
    if not sample or not isinstance(sample, dict):
        return jsonify({"error": "Bad Request", "message": "sample must be a non-empty object."}), 400

    try:
        result = verify_keystroke(
            client_id=g.client.id,
            user_id=str(user_id),
            sample=sample,
        )
    except Exception as exc:  # pragma: no cover
        return jsonify({"error": "Internal Server Error", "message": str(exc)}), 500

    return jsonify({"status": "ok", **result}), 200
