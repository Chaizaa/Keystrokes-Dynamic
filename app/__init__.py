"""
Flask Application Factory with SQLAlchemy, Flask-Login, and Security Extensions
"""

import os
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
    # Use Redis if available (prevents limit bypass in multi-worker deployments).
    # Set REDIS_URL env var in Railway to enable. Falls back to in-memory.
    storage_uri=os.environ.get("REDIS_URL", "memory://"),
)
migrate = Migrate()
cache = Cache()
# SocketIO CORS: use ALLOWED_ORIGIN env var so it matches the REST API CORS policy.
socketio = SocketIO(cors_allowed_origins=os.environ.get("ALLOWED_ORIGIN", "*"))


def create_app(config_name="development"):
    """
    Application factory pattern for Flask

    Args:
        config_name: Configuration environment (development/production/testing) or dict with config values

    Returns:
        Flask application instance
    """
    app = Flask(__name__, template_folder="../templates", static_folder="../static")

    # ProxyFix: Railway (and most cloud platforms) sit behind a reverse proxy.
    # Without this, Flask sees every request as HTTP and Flask-Talisman causes
    # an infinite HTTPS redirect loop.
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

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
        config_class = get_config(config_name)
        # Validate production config before applying (avoids import-time crash)
        if hasattr(config_class, "validate"):
            config_class.validate()
        app.config.from_object(config_class)

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
    # Restrict CORS origins via ALLOWED_ORIGIN env var (Railway: set to your domain).
    # Default is "*" (open) for local dev. In production set e.g.:
    #   ALLOWED_ORIGIN=https://web-production-77b15.up.railway.app
    import os as _cors_os
    _cors_origins = _cors_os.environ.get("ALLOWED_ORIGIN", "*")
    CORS(app, resources={r"/api/*": {"origins": _cors_origins}})

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
        flags = {"DEV_LENIENT_RATELIMIT": app.config.get("DEV_LENIENT_RATELIMIT", False)}
        # In non-production mode Talisman is not initialized, so csp_nonce() would
        # be undefined in templates. Provide a no-op fallback so templates that
        # use {{ csp_nonce() }} still render correctly in development.
        if config_name != "production":
            flags["csp_nonce"] = lambda: ""
        return flags

    # Security Headers (only in production)
    if config_name == "production":
        Talisman(
            app,
            force_https=True,
            strict_transport_security=True,
            session_cookie_secure=True,
            # Nonce is auto-generated per request by Talisman and injected into
            # templates as csp_nonce(). Inline <script> tags must carry
            # nonce="{{ csp_nonce() }}" to be allowed. 'unsafe-inline' is removed
            # so injected scripts (XSS) are blocked even if CSP is somehow bypassed.
            content_security_policy={
                "default-src": "'self'",
                "script-src":  "'self'",  # nonce added automatically via nonce_in
                "style-src":   ["'self'", "'unsafe-inline'"],  # inline styles kept
                "img-src":     ["'self'", "data:"],
            },
            content_security_policy_nonce_in=["script-src"],
        )

    # Register blueprints
    from app.blueprints.admin import admin_bp
    from app.blueprints.api import api_bp
    from app.blueprints.auth import auth_bp
    from app.blueprints.dataset import dataset_bp
    from app.blueprints.health import health_bp
    from app.blueprints.main import main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(dataset_bp)
    # Health endpoints for admins/ops
    app.register_blueprint(health_bp, url_prefix="/health")

    # Exempt admin API from CSRF (for AJAX requests)
    csrf.exempt(admin_bp)

    # Create database tables (guarded so migrations/stamping can run cleanly).
    # When running `flask db ...`, pre-creating tables can break migrations.
    import sys as _sys
    _argv = " ".join(_sys.argv).lower()
    _running_db_cli = (" db " in f" {_argv} ") and any(
        cmd in _argv
        for cmd in (
            "upgrade",
            "downgrade",
            "revision",
            "migrate",
            "merge",
            "stamp",
            "heads",
            "history",
            "current",
            "show",
        )
    )

    if not (app.config.get("SKIP_CREATE_ALL", False) or _running_db_cli):
        with app.app_context():
            db.create_all()

    # -------------------------------------------------------------------------
    # Public-mode lockdown
    # Set  DATASET_ONLY=1  in Railway env vars to expose ONLY /dataset publicly.
    # All other routes return 404 so their existence is not revealed.
    # Allowed prefixes:
    #   /dataset        — the collection page
    #   /api/dataset/   — AJAX endpoints used by dataset_capture.js
    #   /static/        — CSS / JS / image assets
    #   /health/        — Railway health-check pings
    # -------------------------------------------------------------------------
    import os as _os
    if _os.environ.get("DATASET_ONLY") == "1":
        _ALLOWED_PREFIXES = ("/dataset", "/api/dataset/", "/static/", "/health/")

        @app.before_request
        def _dataset_only_guard():
            from flask import abort, request as _req
            p = _req.path
            if not any(p == prefix.rstrip("/") or p.startswith(prefix)
                       for prefix in _ALLOWED_PREFIXES):
                abort(404)

    return app
