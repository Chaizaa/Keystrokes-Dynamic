"""API key authentication guard for external-facing endpoints."""

import hashlib
from functools import wraps

from flask import g, jsonify, request

from app.models import Client


def require_api_key():
    """Authenticate the current request via API key.

    Designed for use as a :func:`flask.Blueprint.before_request` handler::

        @api.before_request
        def authenticate():
            return require_api_key()

    Reads the ``Authorization`` header and expects the format::

        Authorization: Bearer <api_key>

    The raw key is hashed with SHA-256 and looked up against active
    :class:`~app.models.Client` records.

    Returns:
        ``None`` if authentication succeeds (Flask proceeds to the route).
        A ``(Response, 401)`` tuple when authentication fails.

    Side-effects:
        On success, stores the matched :class:`~app.models.Client` in
        :data:`flask.g.client` so route handlers can access it.
    """
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        return (
            jsonify({"error": "Unauthorized", "message": "Missing or malformed Authorization header."}),
            401,
        )

    raw_key = auth_header[len("Bearer "):]

    if not raw_key:
        return (
            jsonify({"error": "Unauthorized", "message": "API key must not be empty."}),
            401,
        )

    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    client = Client.query.filter_by(api_key_hash=key_hash, is_active=True).first()

    if client is None:
        return (
            jsonify({"error": "Unauthorized", "message": "Invalid or inactive API key."}),
            401,
        )

    g.client = client
    return None  # signals Flask to proceed to the route handler


def require_api_key_decorator(f):
    """Route-level decorator equivalent of :func:`require_api_key`.

    Useful when only specific routes inside a blueprint need API-key auth
    rather than the whole blueprint::

        @some_bp.route("/secure")
        @require_api_key_decorator
        def secure_view():
            ...
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        result = require_api_key()
        if result is not None:
            return result
        return f(*args, **kwargs)

    return wrapper
