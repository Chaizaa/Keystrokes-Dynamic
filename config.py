import os
from datetime import timedelta

from dotenv import load_dotenv

# Load environment variables from .env file
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))

_ALLOWED_SAMESITE_VALUES = {"Lax", "Strict", "None"}


class Config:
    """Base configuration"""

    # Flask Core
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key-change-in-prod"

    # Database
    DATABASE_TYPE = os.environ.get("DATABASE_TYPE", "sqlite")
    DATABASE_PATH = os.environ.get("DATABASE_PATH", "data/biometric_auth.db")

    # SQLAlchemy (for future migration)
    if DATABASE_TYPE == "sqlite":
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(basedir, DATABASE_PATH)}"
    else:
        SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session Configuration
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "False") == "True"
    SESSION_COOKIE_HTTPONLY = os.environ.get("SESSION_COOKIE_HTTPONLY", "True") == "True"
    SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")
    PERMANENT_SESSION_LIFETIME = timedelta(
        seconds=int(os.environ.get("PERMANENT_SESSION_LIFETIME", "3600"))
    )

    # Biometric Settings
    # Keep the enrollment target modest so the UX does not require an
    # excessive sample count before login becomes available.
    MIN_ENROLLMENT_SAMPLES = int(os.environ.get("MIN_ENROLLMENT_SAMPLES", "10"))
    RECOMMENDED_SAMPLES = int(os.environ.get("RECOMMENDED_SAMPLES", str(MIN_ENROLLMENT_SAMPLES)))
    VERIFICATION_THRESHOLD = float(os.environ.get("VERIFICATION_THRESHOLD", "0.7"))
    MAX_LOGIN_ATTEMPTS = int(os.environ.get("MAX_LOGIN_ATTEMPTS", "5"))
    _ml_backend_raw = (os.environ.get("ML_BACKEND", "rf") or "rf").strip().lower()
    ML_BACKEND = _ml_backend_raw if _ml_backend_raw in {"rf", "svm"} else "rf"

    # Email verification expiry (hours)
    EMAIL_VERIFICATION_EXPIRY_HOURS = int(os.environ.get("EMAIL_VERIFICATION_EXPIRY_HOURS", "1"))

    # Rate Limiting
    RATELIMIT_ENABLED = os.environ.get("RATELIMIT_ENABLED", "True") == "True"
    RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "100 per hour")
    RATELIMIT_STORAGE_URL = os.environ.get("RATELIMIT_STORAGE_URL", "memory://")

    # Development toggles
    # When True, client-side behavior is lenient (retries on 429/network issues and shorter debounces)
    DEV_LENIENT_RATELIMIT = os.environ.get("DEV_LENIENT_RATELIMIT", "False") == "True"

    # Email (Flask-Mail compatible)
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "1025"))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "False") == "True"
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL", "False") == "True"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@localhost")

    # Example Gmail configuration (recommended: use App Password if your account has 2FA)
    # For TLS (recommended):
    # MAIL_SERVER = 'smtp.gmail.com'
    # MAIL_PORT = 587
    # MAIL_USE_TLS = True
    # MAIL_USE_SSL = False
    # MAIL_USERNAME = 'your@gmail.com'
    # MAIL_PASSWORD = 'your-app-password'
    # MAIL_DEFAULT_SENDER = 'noreply@yourdomain.com'
    # For SSL (alternate):
    # MAIL_SERVER = 'smtp.gmail.com'
    # MAIL_PORT = 465
    # MAIL_USE_TLS = False
    # MAIL_USE_SSL = True
    # MAIL_USERNAME = 'your@gmail.com'
    # MAIL_PASSWORD = 'your-app-password'
    # Note: Google may block plain username/password SMTP. Create an App Password at
    # https://myaccount.google.com/security -> App passwords and use it as MAIL_PASSWORD.

    # Logging
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    LOG_FILE = os.environ.get("LOG_FILE", "app.log")

    # Request size limit — prevents oversized payload attacks on /submit etc.
    # 1 MB is generous for keystroke data (a full 100-rep session is ~50 KB JSON).
    MAX_CONTENT_LENGTH = 1 * 1024 * 1024  # 1 MB

    # Static & Template Paths
    STATIC_FOLDER = "static"
    TEMPLATE_FOLDER = "templates"


class DevelopmentConfig(Config):
    """Development configuration"""

    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False
    # In development we default to lenient client-side rate limit behavior
    DEV_LENIENT_RATELIMIT = True


class ProductionConfig(Config):
    """Production configuration"""

    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True

    # Enforce strong secret key in production
    SECRET_KEY = os.environ.get("SECRET_KEY")

    @classmethod
    def validate(cls):
        validate_config(cls)


class TestingConfig(Config):
    """Testing configuration"""

    DEBUG = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


# Configuration dictionary
config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}


def get_config(config_name=None):
    """Get configuration by name"""
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    return config_by_name.get(config_name, DevelopmentConfig)


def validate_config(config_class):
    """Validate configuration class boundaries before app bootstrap.

    The validator is intentionally conservative and only fails on clearly invalid
    states so existing development flows remain unchanged.
    """
    if config_class is None:
        return

    threshold = float(getattr(config_class, "VERIFICATION_THRESHOLD", 0.7))
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("VERIFICATION_THRESHOLD must be within [0.0, 1.0]")

    min_samples = int(getattr(config_class, "MIN_ENROLLMENT_SAMPLES", 10))
    recommended_samples = int(getattr(config_class, "RECOMMENDED_SAMPLES", min_samples))
    if min_samples <= 0:
        raise ValueError("MIN_ENROLLMENT_SAMPLES must be > 0")
    if recommended_samples < min_samples:
        raise ValueError("RECOMMENDED_SAMPLES must be >= MIN_ENROLLMENT_SAMPLES")

    samesite = str(getattr(config_class, "SESSION_COOKIE_SAMESITE", "Lax"))
    if samesite not in _ALLOWED_SAMESITE_VALUES:
        raise ValueError("SESSION_COOKIE_SAMESITE must be one of: Lax, Strict, None")

    # Keep the existing production-only secret key requirement.
    if config_class is ProductionConfig:
        secret_key = getattr(config_class, "SECRET_KEY", None)
        if not secret_key or secret_key == "dev-secret-key-change-in-prod":
            raise ValueError(
                "SECRET_KEY environment variable must be set in production. "
                "Generate one with: python -c 'import secrets; print(secrets.token_hex(32))'"
            )


RF_MODEL_ENABLED = os.getenv("RF_MODEL_ENABLED", "false").lower() == "true"
RF_MODEL_PATH = os.getenv("RF_MODEL_PATH", "models/rf_default.joblib")
