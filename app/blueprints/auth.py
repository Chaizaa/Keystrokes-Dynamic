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
    """Enter the 6-digit code sent to the account's email.

    Identity is bound server-side in the session (``pwreset_uid``) by the
    initiation endpoint — never via a URL/query param — so the username/email
    never travels in the address bar. If there is no active reset session, send
    the user back to login rather than rendering a dead form.

    A logged-in user (dashboard-initiated reset) stays authenticated throughout:
    if they abandon the flow they remain logged in (no needless re-auth), and a
    *completed* reset logs every session out via the session_token_version bump
    in /api/reset_password. The reset binding lives independently of the auth
    session, so the two never collide.
    """
    if not session.get("pwreset_uid"):
        return redirect(url_for("auth.login_page"))
    return render_template("reset_verify_code.html")


@auth_bp.route("/reset/complete")
def reset_complete_page():
    """Set a new master password and re-enroll biometrics.

    Requires a verified reset session (both the account binding and the signed
    token issued by /api/verify_reset); otherwise redirect to login. As above, a
    logged-in user stays logged in until the reset actually completes.
    """
    if not (session.get("pwreset_uid") and session.get("pwreset_token")):
        return redirect(url_for("auth.login_page"))
    return render_template("reset_complete.html")


@auth_bp.route("/2fa/verify")
def two_factor_verify_page():
    """2FA challenge page shown after username/password + biometric login succeeds."""
    username = request.args.get("username") or session.get("2fa_username", "")
    if not username and not session.get("2fa_user_id"):
        return redirect(url_for("auth.login_page"))
    return render_template("two_factor_verify.html", username=username)


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
