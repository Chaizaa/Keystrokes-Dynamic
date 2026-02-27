from functools import wraps
from datetime import datetime, timezone
import json
import traceback

from flask import Blueprint, render_template
from flask_login import current_user, login_required

from app.models import db, User, AdminAudit

admin_bp = Blueprint("admin", __name__)


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
    # Gather basic metrics and recent audits
    try:
        from sqlalchemy import select
        users = db.session.execute(
            select(User).order_by(User.created_at.desc()).limit(500)
        ).scalars().all()
    except Exception:
        users = []

    try:
        from sqlalchemy import select
        audits = db.session.execute(
            select(AdminAudit).order_by(AdminAudit.timestamp.desc()).limit(100)
        ).scalars().all()
    except Exception:
        audits = []

    # Render a simple admin dashboard template
    return render_template("admin/index.html", users=users, audits=audits)


@admin_bp.route('/user/<int:user_id>/send_reset', methods=['POST'])
@admin_required
def admin_send_reset(user_id):
    from flask import jsonify, url_for
    from datetime import datetime, timezone
    from app.services.email_service import email_service
    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        if not user.email:
            return jsonify({'success': False, 'message': 'User has no email'}), 400

        # Generate a signed token (no visible code) and store sent timestamp in the
        # dedicated password_reset_sent_at column so it doesn't interfere with the
        # email-verification flow that uses email_verification_sent_at.
        sent_at = datetime.now(timezone.utc)
        try:
            # Write to password_reset_sent_at (not email_verification_sent_at)
            user.password_reset_sent_at = sent_at
            # Clear any stale reset code hash
            user.password_reset_code_hash = None
        except Exception:
            pass
        db.session.commit()

        # Use a dedicated salt for password-reset tokens so they are only valid
        # when verified with the same salt on the reset flow.
        token = email_service.generate_token(user.email, salt="password-reset", sent_at=sent_at)
        sent = email_service.send_verification_email(user, token, purpose="admin_reset")

        # Audit the admin action (do not include sensitive user fields in details)
        try:
            a = AdminAudit(
                user_id=current_user.id,
                username=current_user.username,
                action='admin_send_reset',
                details=json.dumps({'target_user_id': user.id}),
            )
            db.session.add(a)
            db.session.commit()
        except Exception:
            db.session.rollback()

        if not sent:
            return jsonify({'success': False, 'message': 'Failed to send email'}), 500
        # Do NOT expose the verification URL or token in API responses for security.
        return jsonify({'success': True, 'message': 'Verification email sent'}), 200
    except Exception as e:
        print(f"[ERROR] admin_send_reset: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Server error'}), 500


@admin_bp.route('/user/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    from flask import jsonify
    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404

        # Prevent deleting the last admin
        try:
            from sqlalchemy import func, select
            admin_count = db.session.execute(
                select(func.count(User.id)).where(User.role == 'admin')
            ).scalar()
            if user.is_admin() and admin_count <= 1:
                return jsonify({'success': False, 'message': 'Cannot delete the last admin account'}), 400
        except Exception:
            pass

        # Remove related audit entries and vectors explicitly to avoid FK issues
        try:
            # Delete AdminAudit entries referencing this user
            from sqlalchemy import delete as sa_delete
            db.session.execute(
                sa_delete(AdminAudit).where(
                    (AdminAudit.user_id == user.id) | (AdminAudit.username == user.username)
                )
            )
        except Exception:
            db.session.rollback()

        try:
            # Delete UsersVector records for this user (enrollment + login samples)
            from app.models import UsersVector
            from sqlalchemy import delete as sa_delete

            db.session.execute(
                sa_delete(UsersVector).where(UsersVector.username == user.username)
            )
        except Exception:
            # Models may not exist in some legacy schemas; ignore failures and continue
            db.session.rollback()

        # Finally delete the user row
        try:
            from sqlalchemy import delete as sa_delete
            db.session.execute(sa_delete(User).where(User.id == user.id))
            db.session.commit()
        except Exception:
            db.session.rollback()
            return jsonify({'success': False, 'message': 'Failed to delete user'}), 500

        # Record admin audit for deletion (do not include personal data)
        try:
            a = AdminAudit(user_id=current_user.id, username=current_user.username, action='admin_delete_user', details=json.dumps({'target_user_id': user_id}))
            db.session.add(a)
            db.session.commit()
        except Exception:
            db.session.rollback()

        return jsonify({'success': True, 'message': 'User deleted'}), 200
    except Exception as e:
        print(f"[ERROR] admin_delete_user: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Server error'}), 500


# NOTE: `/admin/register` endpoint removed. Use scripts/create_admin_manual.py
# for developer-only admin creation/promotion.


@admin_bp.route("/login", methods=["GET"])
def admin_login_page():
    # Public admin login page (separate from main /login)
    return render_template("admin/login.html")


@admin_bp.route("/login", methods=["POST"])
def admin_login():
    from flask import request, jsonify
    from app.services.auth_service import AuthService

    try:
        data = request.get_json() or {}
        username = (data.get("username") or "").strip()
        password = data.get("password")

        if not username or not password:
            return jsonify({"success": False, "message": "Username and password required"}), 400

        from sqlalchemy import select
        user = db.session.execute(select(User).where(User.username == username)).scalars().first()
        if not user or not user.is_admin():
            return jsonify({"success": False, "message": "Unauthorized"}), 403

        if not user.check_password(password):
            return jsonify({"success": False, "message": "Incorrect credentials"}), 403

        auth = AuthService()
        ok = auth.login_user_session(user)
        if not ok:
            return jsonify({"success": False, "message": "Session creation failed"}), 500

        user.last_login = datetime.now(timezone.utc)
        db.session.commit()

        # Audit admin login
        try:
            a = AdminAudit(user_id=user.id, username=user.username, action="admin_login", details=None)
            db.session.add(a)
            db.session.commit()
        except Exception:
            db.session.rollback()

        return jsonify({"success": True, "redirect": "/admin"}), 200
    except Exception as e:
        print(f"[ERROR] admin_login: {e}")
        return jsonify({"success": False, "message": "Server error"}), 500


@admin_bp.route("/diagnostics")
def diagnostics():
    from flask import jsonify
    from sqlalchemy import text
    import os

    info = {"timestamp": datetime.now(timezone.utc).isoformat()}
    try:
        inspector = db.inspect(db.engine)
    except Exception as e:
        return (
            jsonify({"status": "error", "message": "Database unreachable", "details": str(e)}),
            503,
        )

    try:
        if "alembic_version" in inspector.get_table_names():
            with db.engine.connect() as conn:
                res = conn.execute(text("SELECT version_num FROM alembic_version"))
                row = res.fetchone()
                info["alembic_revision"] = row[0] if row else None
        else:
            info["alembic_revision"] = None
    except Exception:
        info["alembic_revision_error"] = "error_fetching"

    try:
        migrations_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "migrations", "versions"))
        files = sorted([f for f in os.listdir(migrations_dir) if f.endswith(".py")])
        info["latest_migration_file"] = files[-1] if files else None
        info["migration_files_count"] = len(files)
    except Exception:
        info["latest_migration_file"] = None
        info["migration_files_count"] = 0

    try:
        cols = {c["name"] for c in inspector.get_columns("users")}
        info["required_user_columns_present"] = all(c in cols for c in ("email", "email_verified", "two_factor_enabled"))
        info["user_columns"] = sorted(list(cols))
    except Exception:
        info["required_user_columns_present"] = False
        info["user_columns"] = []

    return jsonify(info), 200

