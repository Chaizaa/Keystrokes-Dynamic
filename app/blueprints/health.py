"""
Health-related endpoints (migrations/health checks)
"""

from flask import Blueprint, jsonify
from sqlalchemy import text

from app.models import db

health_bp = Blueprint("health", __name__)

# Columns that must be present for registration/email/2FA features to work
REQUIRED_USER_COLUMNS = {"email", "email_verified", "two_factor_enabled"}


@health_bp.route("/live", methods=["GET"])
def live_health():
    """Simple liveness probe for container/process health."""
    return jsonify({"status": "ok", "message": "service is alive"}), 200


@health_bp.route("/ready", methods=["GET"])
def ready_health():
    """Readiness probe that verifies DB connectivity."""
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Service is running but database is not ready.",
                }
            ),
            503,
        )

    return jsonify({"status": "ok", "message": "service is ready"}), 200


@health_bp.route("/migrations", methods=["GET"])
def migrations_health():
    """Report whether the database has the required migration columns.

    Returns 200 with status 'ok' when all required columns are present.
    Returns 503 with details when columns are missing (helpful admin message).
    """
    try:
        inspector = db.inspect(db.engine)
        tables = {t for t in inspector.get_table_names()}
    except Exception:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Could not inspect database. Ensure the database is reachable.",
                }
            ),
            503,
        )

    if "users" not in tables:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Required table 'users' not found. Is the database initialized?",
                }
            ),
            503,
        )

    try:
        cols = {c["name"] for c in inspector.get_columns("users")}
    except Exception:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Could not introspect 'users' table columns.",
                }
            ),
            503,
        )

    missing = sorted(list(REQUIRED_USER_COLUMNS - cols))
    if missing:
        return (
            jsonify(
                {
                    "status": "migrations_out_of_date",
                    "missing_columns": missing,
                    "message": "Database migrations appear to be out of date. Please run `alembic upgrade head` on this environment.",
                }
            ),
            503,
        )

    return (
        jsonify(
            {
                "status": "ok",
                "message": "Required migration columns are present.",
                "checked_columns": sorted(list(REQUIRED_USER_COLUMNS)),
            }
        ),
        200,
    )
