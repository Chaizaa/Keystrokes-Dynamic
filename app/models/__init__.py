"""
Database models package
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Import models for easy access
from .user import User
from .keystroke_vector import KeystrokeVector
from .login_attempt import LoginAttempt

__all__ = ['db', 'User', 'KeystrokeVector', 'LoginAttempt']
