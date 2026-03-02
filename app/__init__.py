"""
Flask Application Factory with SQLAlchemy, Flask-Login, and Security Extensions
"""

import secrets

from flask import Flask
from flask_caching import Cache
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_socketio import SocketIO
from flask_talisman import Talisman
from flask_wtf.csrf import CSRFProtect

# Initialize extensions (without app)
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)
migrate = Migrate()
cache = Cache()
socketio = SocketIO(cors_allowed_origins="*")


def create_app(config_name="development"):
    """
    Application factory pattern for Flask

    Args:
        config_name: Configuration environment (development/production/testing) or dict with config values

    Returns:
        Flask application instance
    """
    app = Flask(__name__, template_folder="../templates", static_folder="../static")

    # Load configuration
    import os
    import sys

    # Add parent directory to path so we can import config
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from config import get_config

    # Handle both string config name and dict config
    if isinstance(config_name, dict):
        app.config.update(config_name)
    else:
        app.config.from_object(get_config(config_name))

    # Set secret key for session management
    if not app.config.get("SECRET_KEY"):
        app.secret_key = secrets.token_hex(32)

    # CSRF Configuration - allow tokens from headers
    app.config["WTF_CSRF_CHECK_DEFAULT"] = True
    app.config["WTF_CSRF_HEADERS"] = ["X-CSRFToken", "X-CSRF-Token"]
    app.config["WTF_CSRF_TIME_LIMIT"] = None  # No expiration for development

    # Initialize database
    from app.models import db

    db.init_app(app)
    migrate.init_app(app, db)

    # Initialize Email
    from app.services.email_service import EmailService

    EmailService.init_mail(app)

    # Initialize Cache
    cache.init_app(
        app,
        config={
            "CACHE_TYPE": app.config.get("CACHE_TYPE", "SimpleCache"),
            "CACHE_DEFAULT_TIMEOUT": app.config.get("CACHE_DEFAULT_TIMEOUT", 300),
            "CACHE_REDIS_URL": app.config.get("CACHE_REDIS_URL"),
        },
    )

    # Initialize SocketIO
    socketio.init_app(app)

    # Initialize extensions
    CORS(app)

    # Flask-Login configuration
    login_manager.init_app(app)
    login_manager.login_view = "auth.login_page"  # Redirect to login page
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User

        return db.session.get(User, int(user_id))

    # CSRF Protection (exempt API routes)
    csrf.init_app(app)

    # Exempt API blueprint from CSRF (for AJAX/fetch requests)
    from app.blueprints.api import api_bp as api_blueprint

    csrf.exempt(api_blueprint)

    # Also exempt v1 API routes if present (safe import)
    try:
        from app.api.routes import api_bp as api_routes_bp

        csrf.exempt(api_routes_bp)
    except Exception:
        # If our new module isn't present yet, continue silently
        pass

    # Rate Limiting
    # Respect application config to enable/disable rate limiting during tests
    if not app.config.get("RATELIMIT_ENABLED", True):
        limiter.enabled = False
        # Clear default limits so they don't apply
        try:
            limiter.default_limits = []
        except Exception:
            pass
    limiter.init_app(app)
    limiter.enabled = app.config.get("RATELIMIT_ENABLED", True)

    # Developer convenience: if DEV_LENIENT_RATELIMIT is enabled, turn off server-side rate limiting
    if app.config.get("DEV_LENIENT_RATELIMIT", False):
        print("[INFO] DEV_LENIENT_RATELIMIT is enabled — disabling server-side rate limiter")
        limiter.enabled = False
        try:
            limiter.default_limits = []
        except Exception:
            pass

    # Inject development toggles into templates
    @app.context_processor
    def inject_dev_flags():
        return {"DEV_LENIENT_RATELIMIT": app.config.get("DEV_LENIENT_RATELIMIT", False)}

    # Security Headers (only in production)
    if config_name == "production":
        Talisman(
            app,
            force_https=True,
            strict_transport_security=True,
            session_cookie_secure=True,
            content_security_policy={
                "default-src": "'self'",
                "script-src": ["'self'", "'unsafe-inline'"],
                "style-src": ["'self'", "'unsafe-inline'"],
            },
        )

    # Register blueprints
    from app.blueprints.admin import admin_bp
    from app.blueprints.api import api_bp
    from app.blueprints.auth import auth_bp
    from app.blueprints.health import health_bp
    from app.blueprints.main import main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # Register API v1 blueprint from `app.api.routes` if available and not registered
    try:
        from app.api.routes import api_bp as api_v1_bp

        if api_v1_bp.name not in app.blueprints:
            app.register_blueprint(api_v1_bp, url_prefix="/api/v1")
    except Exception:
        # Don't block app startup if import fails
        pass
    # Health endpoints for admins/ops
    app.register_blueprint(health_bp, url_prefix="/health")

    # Exempt admin API from CSRF (for AJAX requests)
    csrf.exempt(admin_bp)

    # Create database tables
    with app.app_context():
        db.create_all()
        # Ensure `api_secret_encrypted` column exists (runtime patch for older DBs).
        try:
            from sqlalchemy import inspect, text

            insp = inspect(db.engine)
            if insp.has_table("api_credentials"):
                cols = [c["name"] for c in insp.get_columns("api_credentials")]
                if "api_secret_encrypted" not in cols:
                    # SQLite supports ADD COLUMN; use a safe BEGIN block so this
                    # runs once at startup and doesn't require Alembic for quick fixes.
                    try:
                        with db.engine.begin() as conn:
                            conn.execute(text("ALTER TABLE api_credentials ADD COLUMN api_secret_encrypted TEXT"))
                        print("[INFO] Added api_secret_encrypted column to api_credentials table")
                    except Exception as _e:
                        print("[WARN] Failed to add api_secret_encrypted column:", _e)
        except Exception:
            # If inspection fails, do not block app startup.
            pass

    return app
