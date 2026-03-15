"""
Shared state for the api blueprint package.

All route modules import ``api_bp``, ``auth_service``, and ``biometric_service``
from here so there is exactly one instance of each.
"""

from flask import Blueprint

from app import limiter
from app.services import AuthService, BiometricService

api_bp = Blueprint("api", __name__)

# Service layer
auth_service = AuthService()
biometric_service = BiometricService()
