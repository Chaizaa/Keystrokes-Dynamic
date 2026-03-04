"""
Main Blueprint - Landing pages and general routes
"""

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

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


@main_bp.route("/dashboard/api-key", methods=["GET", "POST"])
@login_required
def api_key_dashboard():
    """API key management page.

    GET  — show whether the current user has an API key.
    POST — (re-)generate an API key; display the raw key exactly once.
    """
    from app.models import Client, db

    client = Client.query.filter_by(name=current_user.username).first()

    new_raw_key = None  # shown once on POST, never persisted

    if request.method == "POST":
        if client is None:
            client = Client(name=current_user.username, api_key_hash="placeholder")
            db.session.add(client)

        new_raw_key = client.generate_api_key()
        db.session.commit()

    has_key = client is not None and client.api_key_hash not in (None, "", "placeholder")
    return render_template(
        "api_key_dashboard.html",
        has_key=has_key,
        new_raw_key=new_raw_key,
    )


