"""
Flask Application Factory with SQLAlchemy, Flask-Login, and Security Extensions
"""

import os
import uuid
import secrets
import sys

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


def _load_app_config(app, config_name):
    """Load app config from dict or named config class."""
    # Add parent directory to path so we can import config
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from config import get_config, validate_config

    # Handle both string config name and dict config
    if isinstance(config_name, dict):
        app.config.update(config_name)
        return

    config_class = get_config(config_name)
    validate_config(config_class)
    app.config.from_object(config_class)


def _configure_rate_limiter(app):
    """Configure and initialize Flask-Limiter based on app config toggles."""
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


def _register_blueprints(app):
    """Register all application blueprints in the established order."""
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


def _attach_service_registry(app):
    """Attach the shared API service registry to app.extensions."""
    from app.blueprints.api._shared import service_registry as api_service_registry

    app.extensions["service_registry"] = api_service_registry


def _is_running_db_cli():
    """Detect whether current process is running flask db CLI commands."""
    argv_text = " ".join(sys.argv).lower()
    return (" db " in f" {argv_text} ") and any(
        cmd in argv_text
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


def _should_run_create_all(app):
    """Return True if create_all should run for this process context."""
    return not (
        app.config.get("SKIP_CREATE_ALL", False)
        or app.config.get("TESTING", False)
        or _is_running_db_cli()
    )


def _configure_dataset_only_guard(app):
    """Optionally expose only dataset-related routes for public collection mode."""
    if os.environ.get("DATASET_ONLY") != "1":
        return

    _ALLOWED_PREFIXES = ("/dataset", "/api/dataset/", "/static/", "/health/")

    @app.before_request
    def _dataset_only_guard():
        from flask import abort, request as _req

        p = _req.path
        if not any(p == prefix.rstrip("/") or p.startswith(prefix) for prefix in _ALLOWED_PREFIXES):
            abort(404)


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
    _load_app_config(app, config_name)

    # Normalize ML backend mode switch so app runtime always sees a valid value.
    # Accept 'rf', 'svm', 'statistical' (plus aliases 'stat'/'template' yang akan
    # di-normalize ke 'statistical' di BiometricService._normalize_backend_name).
    _ml_backend_raw = str(app.config.get("ML_BACKEND", os.environ.get("ML_BACKEND", "rf")) or "rf").strip().lower()
    _valid_backends = {"rf", "svm", "statistical", "stat", "template"}
    app.config["ML_BACKEND"] = _ml_backend_raw if _ml_backend_raw in _valid_backends else "rf"

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
    _cors_origins = os.environ.get("ALLOWED_ORIGIN", "*")
    CORS(app, resources={r"/api/*": {"origins": _cors_origins}})

    # Flask-Login configuration
    login_manager.init_app(app)
    login_manager.login_view = "auth.login_page"  # Redirect to login page
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        from flask import session
        from app.models import User
        if isinstance(user_id, str):
            try:
                user_id = uuid.UUID(user_id)
            except ValueError:
                return None
        user = db.session.get(User, user_id)
        if user is None:
            return None
        # Reject sessions issued before the user's session_token_version was
        # bumped (e.g. by a password reset). Sessions without a snapshot (legacy
        # cookies predating this field) are left intact so we don't mass-logout
        # on deploy; new logins always carry the snapshot.
        stv = session.get("stv")
        if stv is not None and stv != user.session_token_version:
            return None
        return user

    # CSRF Protection (exempt API routes)
    csrf.init_app(app)

    # Exempt API blueprint from CSRF (for AJAX/fetch requests)
    from app.blueprints.api import api_bp as api_blueprint

    csrf.exempt(api_blueprint)

    # Rate Limiting
    _configure_rate_limiter(app)

    # Inject development toggles into templates
    @app.context_processor
    def inject_dev_flags():
        flags = {
            "DEV_LENIENT_RATELIMIT": app.config.get("DEV_LENIENT_RATELIMIT", False),
            "RECOMMENDED_SAMPLES": int(app.config.get("RECOMMENDED_SAMPLES", 30)),
        }
        # Templates reference {{ csp_nonce() }}. The production CSP below uses
        # 'unsafe-inline' (not per-request nonces) because the app relies on many
        # inline event handlers, so provide a no-op csp_nonce() in every
        # environment to keep templates rendering.
        flags["csp_nonce"] = lambda: ""
        return flags

    # Security Headers (only in production)
    if config_name == "production":
        Talisman(
            app,
            force_https=True,
            strict_transport_security=True,
            session_cookie_secure=True,
            # 'unsafe-inline' is allowed for scripts because the templates use
            # many inline event handlers (onclick/onsubmit/onpaste/...) which a
            # nonce-based CSP cannot cover without a large refactor. Sources are
            # still restricted to 'self' (no external script/style origins), and
            # the strong transit protections below (HTTPS, HSTS, secure cookies)
            # remain in force. Tighten to nonce-based CSP later if the inline
            # handlers are refactored.
            content_security_policy={
                "default-src": "'self'",
                "script-src":  ["'self'", "'unsafe-inline'"],
                "style-src":   ["'self'", "'unsafe-inline'"],
                "img-src":     ["'self'", "data:"],
            },
            referrer_policy="strict-origin-when-cross-origin",
        )

    # Register blueprints
    _register_blueprints(app)

    # Expose shared service registry through app extensions.
    _attach_service_registry(app)

    # Admin blueprint: CSRF is NOT exempted. base.html's global fetch() override
    # automatically injects X-CSRFToken on every non-GET request, so all admin
    # AJAX calls (delete user, send reset) are protected without any extra work.

    # Create database tables (guarded so migrations/stamping can run cleanly).
    # When running `flask db ...`, pre-creating tables can break migrations.
    if _should_run_create_all(app):
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
    _configure_dataset_only_guard(app)

    return app
