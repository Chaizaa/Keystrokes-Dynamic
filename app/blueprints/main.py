"""
Main Blueprint - Landing pages and general routes
"""

from flask import Blueprint, redirect, render_template, session, url_for, jsonify, request, current_app
from flask_login import current_user, login_required

from app.services.api_credentials import (
    ensure_api_credential,
    get_active_credential_for_user,
    rotate_credential,
    revoke_credential,
)

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    """Landing page"""
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))
    return render_template("landing.html")


@main_bp.route("/home")
@login_required  # Flask-Login protection
def home():
    """Dashboard/Home page - requires login"""
    return render_template("dashboard.html")


@main_bp.route("/dashboard/api/credential", methods=["GET"])
@login_required
def dashboard_get_api_credential():
    """Return metadata and, if configured, the decrypted API secret for UI display.

    WARNING: returning raw API secrets to the UI reduces security. This endpoint
    will only include `api_secret_raw` when the application configuration
    provides a valid `API_SECRET_ENC_KEY`. In production ensure the key is
    securely managed.
    """
    cred = get_active_credential_for_user(current_user)
    if not cred:
        return jsonify({"has_credential": False}), 200
    # Mask API key by default for safety
    masked = "".join([c if i < 6 else "•" for i, c in enumerate(cred.api_key)])

    result = {
        "has_credential": True,
        "api_key": cred.api_key,
        "masked_secret": masked,
        "created_at": cred.created_at.isoformat() if cred.created_at else None,
        "last_used_at": cred.last_used_at.isoformat() if cred.last_used_at else None,
        "is_active": bool(cred.is_active),
    }

    # If encryption key present, attempt to decrypt stored secret so UI can
    # display it persistently. If cryptography isn't installed or decryption
    # fails, we silently omit the raw secret.
    key = current_app.config.get("API_SECRET_ENC_KEY")
    if key and cred.api_secret_encrypted:
        try:
            from cryptography.fernet import Fernet
            f = Fernet(key.encode())
            raw = f.decrypt(cred.api_secret_encrypted.encode()).decode()
            result["api_secret_raw"] = raw
        except Exception:
            result["api_secret_raw"] = None

    return jsonify(result)


@main_bp.route("/dashboard/api/credential/generate", methods=["POST"])
@login_required
def dashboard_generate_api_credential():
    """Generate an API credential if the user has none. Returns the raw secret ONCE."""
    pair = ensure_api_credential(current_user)
    if not pair:
        return jsonify({"success": False, "message": "Active credential already exists"}), 200
    api_key, api_secret_raw = pair
    # Return secret only now; server does not persist raw secret
    return jsonify({"success": True, "api_key": api_key, "api_secret_raw": api_secret_raw}), 201


@main_bp.route("/dashboard/api/credential/rotate", methods=["POST"])
@login_required
def dashboard_rotate_api_credential():
    """Rotate (revoke old and create new) credential and return new raw secret once."""
    api_key, api_secret_raw = rotate_credential(current_user)
    return jsonify({"success": True, "api_key": api_key, "api_secret_raw": api_secret_raw}), 200


@main_bp.route("/dashboard/api/credential/revoke", methods=["POST"])
@login_required
def dashboard_revoke_api_credential():
    """Revoke active credentials for the current user."""
    changed = revoke_credential(current_user)
    return jsonify({"success": True, "revoked": bool(changed)})
