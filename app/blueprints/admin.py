from functools import wraps
from datetime import datetime, timezone

from flask import Blueprint, render_template, jsonify, request, current_app
from flask_login import current_user, login_required
from sqlalchemy import select, func, delete

from app.models import db, User, AdminAudit, UsersVector, APIKey, EnrollmentLog, VerificationLog, UserMLModel
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


_USERS_PAGE_SIZE = 25
_AUDITS_PAGE_SIZE = 25


def _clamp_page(raw, total_pages):
    """Parse a ?page param to a 1-based int within [1, total_pages]."""
    try:
        n = int(raw or 1)
    except (TypeError, ValueError):
        n = 1
    if n < 1:
        n = 1
    if total_pages and n > total_pages:
        n = total_pages
    return n


@admin_bp.route("/")
@admin_required
def admin_index():
    """Admin dashboard landing page (paginated users + audits)."""
    total_users = db.session.execute(select(func.count(User.id))).scalar() or 0
    total_audits = db.session.execute(select(func.count(AdminAudit.id))).scalar() or 0
    total_enrollments = db.session.execute(select(func.count(UsersVector.id))).scalar() or 0

    users_pages = max(1, -(-total_users // _USERS_PAGE_SIZE))   # ceil division
    audits_pages = max(1, -(-total_audits // _AUDITS_PAGE_SIZE))

    users_page = _clamp_page(request.args.get("users_page"), users_pages)
    audits_page = _clamp_page(request.args.get("audits_page"), audits_pages)

    users = db.session.execute(
        select(User)
        .order_by(User.created_at.desc())
        .limit(_USERS_PAGE_SIZE)
        .offset((users_page - 1) * _USERS_PAGE_SIZE)
    ).scalars().all()

    audits = db.session.execute(
        select(AdminAudit)
        .order_by(AdminAudit.timestamp.desc())
        .limit(_AUDITS_PAGE_SIZE)
        .offset((audits_page - 1) * _AUDITS_PAGE_SIZE)
    ).scalars().all()

    return render_template(
        "admin/index.html",
        users=users,
        audits=audits,
        total_users=total_users,
        total_audits=total_audits,
        total_enrollments=total_enrollments,
        users_page=users_page,
        users_pages=users_pages,
        users_page_size=_USERS_PAGE_SIZE,
        audits_page=audits_page,
        audits_pages=audits_pages,
        audits_page_size=_AUDITS_PAGE_SIZE,
    )


@admin_bp.route('/user/<uuid:user_id>/send_reset', methods=['POST'])
@admin_required
def admin_send_reset(user_id):
    """Admin action to trigger a password reset for a user."""
    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        if not user.email:
            return jsonify({'success': False, 'message': 'User has no email'}), 400

        # Aware UTC for the signed token; naive UTC for the DB columns
        # (db.DateTime without tz — see verification._utc_naive_now docstring).
        sent_at = datetime.now(timezone.utc)
        sent_at_naive = sent_at.replace(tzinfo=None)
        user.password_reset_sent_at = sent_at_naive
        user.email_verification_sent_at = sent_at_naive
        user.password_reset_code_hash = None
        db.session.commit()

        # Use VerificationService for secure signed token
        token = verification_service.generate_signed_token(
            user.email, salt="password-reset", sent_at=sent_at
        )
        sent = email_service.send_verification_email(user, token, purpose="admin_reset")

        # Centralized logging
        log_audit(
            action=AdminAudit.ACTION_ADMIN_SEND_RESET,
            user_id=current_user.id,
            username=current_user.username,
            details={'target_user_id': str(user.id)}
        )
        db.session.commit()

        if not sent:
            return jsonify({'success': False, 'message': 'Failed to send email'}), 500
        return jsonify({'success': True, 'message': 'Verification email sent'}), 200

    except Exception:
        current_app.logger.exception("admin_send_reset failed")
        return jsonify({'success': False, 'message': 'Server error'}), 500


@admin_bp.route('/user/<uuid:user_id>/delete', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    """Admin action to delete a user and all their associated biometric data."""
    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404

        # Block self-deletion as a second safety net (UI already disables the button)
        if current_user.id == user.id:
            return jsonify({'success': False, 'message': 'Cannot delete your own admin account'}), 400

        # Prevent deleting the last admin
        admin_count = db.session.execute(
            select(func.count(User.id)).where(User.role == 'admin')
        ).scalar() or 0
        if user.is_admin() and admin_count <= 1:
            return jsonify({'success': False, 'message': 'Cannot delete the last admin account'}), 400

        target_username = user.username

        # Atomic deletion of user-related records.
        # Order matters because of layered FKs:
        #   EnrollmentLog / VerificationLog reference BOTH users.id AND api_keys.id,
        #   so they must be cleared before APIKey, which itself FKs users.id.
        try:
            # 1. First, delete all EnrollmentLog/VerificationLog records that reference THIS USER
            db.session.execute(delete(EnrollmentLog).where(EnrollmentLog.user_id == user.id))
            db.session.execute(delete(VerificationLog).where(VerificationLog.user_id == user.id))
            
            # 2. Then, delete logs that reference API KEYS owned by this user (created via partner API)
            #    An API key belongs to this user, but may have been used to enroll/verify OTHER users
            user_api_key_ids = db.session.execute(
                select(APIKey.id).where(APIKey.user_id == user.id)
            ).scalars().all()
            if user_api_key_ids:
                db.session.execute(delete(EnrollmentLog).where(EnrollmentLog.api_key_id.in_(user_api_key_ids)))
                db.session.execute(delete(VerificationLog).where(VerificationLog.api_key_id.in_(user_api_key_ids)))
            
            # 3. Partner-API keys (FK -> users.id, no ondelete)
            db.session.execute(delete(APIKey).where(APIKey.user_id == user.id))
            # 4. Biometric samples + per-user ML model
            db.session.execute(delete(UsersVector).where(UsersVector.username == target_username))
            db.session.execute(delete(UserMLModel).where(UserMLModel.user_id == user.id))
            # 5. Audit logs referencing this user
            db.session.execute(
                delete(AdminAudit).where(
                    (AdminAudit.user_id == user.id) | (AdminAudit.username == target_username)
                )
            )
            # 6. Finally, the user row
            db.session.execute(delete(User).where(User.id == user.id))

            # Centralized logging of the action before commit
            log_audit(
                action=AdminAudit.ACTION_ADMIN_DELETE_USER,
                user_id=current_user.id,
                username=current_user.username,
                details={'target_user_id': str(user_id), 'target_username': target_username}
            )

            db.session.commit()
            return jsonify({'success': True, 'message': 'User deleted'}), 200
        except Exception:
            db.session.rollback()
            current_app.logger.exception("admin_delete_user transaction failed")
            return jsonify({'success': False, 'message': 'Failed to delete user records'}), 500

    except Exception:
        current_app.logger.exception("admin_delete_user failed")
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
        identifier = (data.get("username") or data.get("identifier") or "").strip()
        password = data.get("password")

        if not identifier or not password:
            return jsonify({"success": False, "message": "Username and password required"}), 400

        # Accept either username or email so admins don't have to remember which they enrolled with.
        user = db.session.execute(
            select(User).where((User.username == identifier) | (User.email == identifier))
        ).scalars().first()

        if not user or not user.is_admin():
            return jsonify({"success": False, "message": "Unauthorized"}), 403

        if not user.check_password(password):
            return jsonify({"success": False, "message": "Incorrect credentials"}), 403

        if not _auth_service().login_user_session(user):
            return jsonify({"success": False, "message": "Session creation failed"}), 500

        user.last_login = datetime.now(timezone.utc)
        
        log_audit(
            action=AdminAudit.ACTION_ADMIN_LOGIN,
            user_id=user.id,
            username=user.username
        )
        db.session.commit()

        return jsonify({"success": True, "redirect": "/admin"}), 200
    except Exception:
        current_app.logger.exception("admin_login failed")
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
