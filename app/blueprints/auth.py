"""
Auth Blueprint - Authentication routes (login, register, logout)
"""
from flask import Blueprint, render_template, session, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login')
def login_page():
    """Login page"""
    # Redirect if already logged in
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    return render_template('login_unified.html')

@auth_bp.route('/login/legacy')
def login_legacy():
    """Legacy login page"""
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    return render_template('login.html')

@auth_bp.route('/register')
def register_page():
    """Registration page"""
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    return render_template('register.html')


@auth_bp.route('/verify')
def verify_page():
    """Email verification UI"
    If a username is provided via query params or server-side context, prefill the form.
    """
    # Redirect if already logged in
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))

    from flask import request
    username = request.args.get('username', '')
    return render_template('verify_code.html', username=username)

@auth_bp.route('/logout')
def logout():
    """Logout and clear session"""
    logout_user()  # Flask-Login logout
    session.clear()  # Clear any remaining session data
    flash('Logged out successfully', 'info')
    return redirect(url_for('main.index'))
