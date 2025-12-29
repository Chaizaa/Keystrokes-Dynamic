"""
Service Layer Package
Business logic layer for the application
"""
from app.services.auth_service import AuthService
# Use refactored biometric implementation to avoid legacy indentation issues
from app.services.biometric import BiometricService

__all__ = ['AuthService', 'BiometricService']
