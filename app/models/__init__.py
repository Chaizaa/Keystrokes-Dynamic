"""
Database models package
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from .feature_vector import EnrollmentVector, FeatureVector
from .keystroke_vector import KeystrokeVector
from .login_attempt import LoginAttempt
from .api_credential import APICredential

# Import models for easy access
from .user import User
from .admin_audit import AdminAudit

__all__ = [
    "db",
    "User",
    "KeystrokeVector",
    "LoginAttempt",
    "FeatureVector",
    "EnrollmentVector",
    "AdminAudit",
    "APICredential",
]
