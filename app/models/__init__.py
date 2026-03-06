"""
Database models package
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from .feature_vector import EnrollmentVector, FeatureVector
from .keystroke_vector import KeystrokeVector
from .login_attempt import LoginAttempt

# Import models for easy access
from .user import User
from .admin_audit import AdminAudit
from .api_key import APIKey
from .enrollment_log import EnrollmentLog
from .verification_log import VerificationLog

__all__ = [
    "db",
    "User",
    "KeystrokeVector",
    "LoginAttempt",
    "FeatureVector",
    "EnrollmentVector",
    "AdminAudit",
    "APIKey",
    "EnrollmentLog",
    "VerificationLog",
]
