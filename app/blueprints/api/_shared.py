"""
Shared state for the api blueprint package.

All route modules import ``api_bp``, ``auth_service``, ``biometric_service``,
and ``db_manager`` from here so there is exactly one instance of each.
"""

from flask import Blueprint
from flask_limiter import Limiter

from app import limiter
from app.database import Database
from app.services import AuthService, BiometricService

api_bp = Blueprint("api", __name__)

# Legacy database manager (being phased out – use SQLAlchemy models directly)
db_manager = Database()

# Service layer
auth_service = AuthService()
biometric_service = BiometricService(db=db_manager)
