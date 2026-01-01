from functools import wraps
from datetime import datetime, timezone

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
        users = User.query.order_by(User.created_at.desc()).limit(50).all()
    except Exception:
        users = []

    try:
        audits = (
            AdminAudit.query.order_by(AdminAudit.timestamp.desc()).limit(100).all()
        )
    except Exception:
        audits = []

    # Render a simple admin dashboard template
    return render_template("admin/index.html", users=users, audits=audits)


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

        user = db.session.query(User).filter_by(username=username).first()
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

