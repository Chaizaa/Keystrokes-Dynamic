from functools import wraps
from datetime import datetime, timezone
import json
import traceback

from flask import Blueprint, render_template, jsonify, url_for, request
from flask_login import current_user, login_required
from sqlalchemy import select, func, delete

from app.models import db, User, AdminAudit, UsersVector
from app.services.resolution import resolve_service_from_app
from app.services.email_service import email_service
from app.services.verification_service import verification_service
from app.blueprints.api.helpers import log_audit

admin_bp = Blueprint("admin", __name__)


def _auth_service():
    """Resolve auth service from active app registry."""
    return resolve_service_from_app("auth_service")


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not getattr(current_user, "role", "").lower() == "admin":
            from flask import abort
            abort(403)
        return f(*args, **kwargs)
    return decorated


@admin_bp.route("/")
@admin_required
def admin_index():
    """Admin dashboard landing page."""
    try:
        users = db.session.execute(
            select(User).order_by(User.created_at.desc()).limit(500)
        ).scalars().all()
    except Exception:
        users = []

    try:
        audits = db.session.execute(
            select(AdminAudit).order_by(AdminAudit.timestamp.desc()).limit(100)
        ).scalars().all()
    except Exception:
        audits = []

    return render_template("admin/index.html", users=users, audits=audits)


@admin_bp.route('/user/<int:user_id>/send_reset', methods=['POST'])
@admin_required
def admin_send_reset(user_id):
    """Admin action to trigger a password reset for a user."""
    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        if not user.email:
            return jsonify({'success': False, 'message': 'User has no email'}), 400

        sent_at = datetime.now(timezone.utc)
        user.password_reset_sent_at = sent_at
        user.email_verification_sent_at = sent_at
        user.password_reset_code_hash = None
        db.session.commit()

        # Use VerificationService for secure signed token
        token = verification_service.generate_signed_token(
            user.email, salt="password-reset", sent_at=sent_at
        )
        sent = email_service.send_verification_email(user, token, purpose="admin_reset")

        # Centralized logging
        log_audit(
            action='admin_send_reset',
            user_id=current_user.id,
            username=current_user.username,
            details={'target_user_id': user.id}
        )
        db.session.commit()

        if not sent:
            return jsonify({'success': False, 'message': 'Failed to send email'}), 500
        return jsonify({'success': True, 'message': 'Verification email sent'}), 200

    except Exception as e:
        print(f"[ERROR] admin_send_reset: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Server error'}), 500


@admin_bp.route('/user/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    """Admin action to delete a user and all their associated biometric data."""
    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404

        # Prevent deleting the last admin
        admin_count = db.session.execute(
            select(func.count(User.id)).where(User.role == 'admin')
        ).scalar() or 0
        if user.is_admin() and admin_count <= 1:
            return jsonify({'success': False, 'message': 'Cannot delete the last admin account'}), 400

        # Atomic deletion of user-related records
        try:
            # 1. Delete Audit logs referencing this user (to avoid FK issues)
            db.session.execute(
                delete(AdminAudit).where(
                    (AdminAudit.user_id == user.id) | (AdminAudit.username == user.username)
                )
            )
            # 2. Delete Biometric samples
            db.session.execute(
                delete(UsersVector).where(UsersVector.username == user.username)
            )
            # 3. Delete the user
            db.session.execute(delete(User).where(User.id == user.id))
            
            # Centralized logging of the action before commit
            log_audit(
                action='admin_delete_user',
                user_id=current_user.id,
                username=current_user.username,
                details={'target_user_id': user_id}
            )
            
            db.session.commit()
            return jsonify({'success': True, 'message': 'User deleted'}), 200
        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] Transaction failed for user deletion: {e}")
            return jsonify({'success': False, 'message': 'Failed to delete user records'}), 500

    except Exception as e:
        print(f"[ERROR] admin_delete_user: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Server error'}), 500


@admin_bp.route("/create", methods=["GET"])
@admin_required
def admin_create_page():
    return render_template("admin/register.html")


@admin_bp.route("/login", methods=["GET"])
def admin_login_page():
    return render_template("admin/login.html")


@admin_bp.route("/login", methods=["POST"])
def admin_login():
    try:
        data = request.get_json() or {}
        username = (data.get("username") or "").strip()
        password = data.get("password")

        if not username or not password:
            return jsonify({"success": False, "message": "Username and password required"}), 400

        user = db.session.execute(
            select(User).where(User.username == username)
        ).scalars().first()

        if not user or not user.is_admin():
            return jsonify({"success": False, "message": "Unauthorized"}), 403

        if not user.check_password(password):
            return jsonify({"success": False, "message": "Incorrect credentials"}), 403

        if not _auth_service().login_user_session(user):
            return jsonify({"success": False, "message": "Session creation failed"}), 500

        user.last_login = datetime.now(timezone.utc)
        
        log_audit(
            action="admin_login",
            user_id=user.id,
            username=user.username
        )
        db.session.commit()

        return jsonify({"success": True, "redirect": "/admin"}), 200
    except Exception as e:
        print(f"[ERROR] admin_login: {e}")
        return jsonify({"success": False, "message": "Server error"}), 500


@admin_bp.route("/diagnostics")
@admin_required
def diagnostics():
    """System diagnostic information for admins."""
    from sqlalchemy import text
    import os

    from typing import Any
    info: dict[str, Any] = {"timestamp": datetime.now(timezone.utc).isoformat()}
    try:
        inspector = db.inspect(db.engine)
    except Exception as e:
        return jsonify({"status": "error", "message": "Database unreachable", "details": str(e)}), 503

    # Alembic Revision
    try:
        if "alembic_version" in inspector.get_table_names():
            with db.engine.connect() as conn:
                res = conn.execute(text("SELECT version_num FROM alembic_version"))
                row = res.fetchone()
                info["alembic_revision"] = row[0] if row else None
    except Exception:
        info["alembic_revision"] = "error_fetching"

    # Migration Files
    try:
        migrations_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "migrations", "versions"))
        files = sorted([f for f in os.listdir(migrations_dir) if f.endswith(".py")])
        info["latest_migration_file"] = files[-1] if files else None
        info["migration_files_count"] = len(files)
    except Exception:
        pass

    # DB Integrity Check
    try:
        cols = {c["name"] for c in inspector.get_columns("users")}
        info["required_user_columns_present"] = all(c in cols for c in ("email", "email_verified", "two_factor_enabled"))
        info["user_columns"] = sorted(list(cols))
    except Exception:
        info["required_user_columns_present"] = False

    return jsonify(info), 200
