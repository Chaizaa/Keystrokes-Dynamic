"""
Auth Blueprint - Authentication routes (login, register, logout)
"""

from flask import Blueprint, flash, redirect, render_template, session, url_for, request
from flask_login import current_user, login_user, logout_user

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login")
def login_page():
    """Login page"""
    # Redirect if already logged in, except when this request is part of a reset flow
    # (presence of `reset=1` tells us the caller wants the login UI for reset completion)
    reset_param = request.args.get("reset")
    if current_user.is_authenticated and reset_param != "1":
        return redirect(url_for("main.home"))
    return render_template("login_unified.html")


@auth_bp.route("/register")
def register_page():
    """Registration page"""
    # Allow access to the registration page during a reset flow even if the user is logged in
    reset_param = request.args.get("reset")
    if current_user.is_authenticated and reset_param != "1":
        return redirect(url_for("main.home"))
    return render_template("register.html")


@auth_bp.route("/reset/verify-code")
def reset_verify_code_page():
    """User self-initiated password-reset: enter the 6-digit code sent to their email.
    This is a dedicated page separated from /verify (registration) so the two flows
    never share endpoints or query-param conventions.
    If the user arrives here while already logged in (e.g. they initiated the reset from
    the dashboard), we log them out silently so the rest of the reset flow is clean.
    """
    if current_user.is_authenticated:
        logout_user()
        session.clear()
    username = request.args.get("username", "")
    return render_template("reset_verify_code.html", username=username)


@auth_bp.route("/reset/complete")
def reset_complete_page():
    """Reset completion page - serve the enrollment UI for setting a new master password.
    This route exists so verification can redirect to a dedicated URL rather than re-using
    `/register`. It renders the same enrollment UI but is a distinct page/URL allowing
    clearer UX and future template divergence if desired.
    """
    # Allow logged-in users to access this page during a reset flow
    username = request.args.get("username", "")
    return render_template("reset_complete.html", username=username)


@auth_bp.route("/verify")
def verify_page():
    """Email verification UI for registration only.
    The password-reset verify-code flow uses /reset/verify-code instead.
    """
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))
    username = request.args.get("username", "")
    purpose = request.args.get("purpose", "")
    return render_template("verify_code.html", username=username, purpose=purpose)


@auth_bp.route("/logout")
def logout():
    """Logout and clear session"""
    logout_user()  # Flask-Login logout
    session.clear()  # Clear any remaining session data
    flash("Logged out successfully", "info")
    return redirect(url_for("main.index"))
