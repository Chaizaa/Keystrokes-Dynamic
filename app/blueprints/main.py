"""
Main Blueprint - Landing pages and general routes
"""

from flask import Blueprint, redirect, render_template, session, url_for
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
