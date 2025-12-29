"""Minimal admin blueprint to satisfy app initialization during tests."""
from flask import Blueprint, jsonify
from app.models import db
from sqlalchemy import text
from datetime import datetime, timezone
import os

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/')
def admin_index():
    return 'Admin area'


@admin_bp.route('/diagnostics')
def diagnostics():
    """Return diagnostic info useful for admins/ops.

    - alembic revision (if alembic_version table present)
    - latest migration filename in repo
    - timestamp of check
    - basic migration column presence for 'users' table
    """
    info = {'timestamp': datetime.now(timezone.utc).isoformat()}

    try:
        inspector = db.inspect(db.engine)
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Database unreachable', 'details': str(e)}), 503

    # Alembic revision
    try:
        if 'alembic_version' in inspector.get_table_names():
            with db.engine.connect() as conn:
                res = conn.execute(text('SELECT version_num FROM alembic_version'))
                row = res.fetchone()
                info['alembic_revision'] = row[0] if row else None
        else:
            info['alembic_revision'] = None
    except Exception as e:
        info['alembic_revision_error'] = str(e)

    # Latest migration file present in repo
    try:
        migrations_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'migrations', 'versions'))
        files = sorted([os.path.basename(p) for p in os.listdir(migrations_dir) if p.endswith('.py')])
        info['latest_migration_file'] = files[-1] if files else None
        info['migration_files_count'] = len(files)
    except Exception:
        info['latest_migration_file'] = None
        info['migration_files_count'] = 0

    # Check essential user columns
    try:
        cols = {c['name'] for c in inspector.get_columns('users')}
        info['required_user_columns_present'] = all(c in cols for c in ('email', 'email_verified', 'two_factor_enabled'))
        info['user_columns'] = sorted(list(cols))
    except Exception:
        info['required_user_columns_present'] = False
        info['user_columns'] = []

    return jsonify(info), 200
