"""
Database models package.

Import order matters to avoid circular references:
  1. ``db`` (SQLAlchemy instance) is defined here first.
  2. Individual models import ``db`` from this module.
  3. This module then imports the models so callers can do::

       from app.models import User, UsersVector, AdminAudit, LoginAttempt

Available models:
  - User           — user accounts, auth, 2FA, email verification
  - UsersVector    — keystroke biometric samples (enrollment & login)
  - AdminAudit     — immutable audit trail for all significant actions
  - LoginAttempt   — per-request login attempt log

Deprecated aliases (use UsersVector instead):
  - KeystrokeVector, FeatureVector, EnrollmentVector
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Core models — imported after db is defined to avoid circular imports
from .user import User                                               # noqa: E402
from .keystroke_vector import KeystrokeVector, UsersVector           # noqa: E402
from .feature_vector import EnrollmentVector, FeatureVector          # noqa: E402  (deprecated stubs)
from .admin_audit import AdminAudit                                  # noqa: E402
from .login_attempt import LoginAttempt                              # noqa: E402
from .client import Client                                           # noqa: E402
from .dataset import DatasetSubject, DatasetEntry                    # noqa: E402

__all__ = [
    "db",
    "User",
    "UsersVector",
    "KeystrokeVector",    # deprecated alias → UsersVector
    "FeatureVector",      # deprecated alias → UsersVector
    "EnrollmentVector",   # deprecated alias → UsersVector
    "AdminAudit",
    "LoginAttempt",
    "DatasetSubject",
    "DatasetEntry",
]
