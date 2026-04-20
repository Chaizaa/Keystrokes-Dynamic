"""
Service Layer Package
Business logic layer for the application
"""

from app.services.auth_service import AuthService
from app.services.biometric_service import BiometricService
from app.services.ml_keystroke_verifier import MLKeystrokeVerifier
from app.services.ml_model_service import MLModelService, ml_model_service
from app.services.registry import ServiceRegistry
from app.services.resolution import resolve_service, resolve_service_from_app
from app.services.svm_model_service import SVMModelService, svm_model_service

<<<<<<< HEAD
__all__ = [
	"AuthService",
	"BiometricService",
	"MLKeystrokeVerifier",
	"MLModelService",
	"ml_model_service",
	"ServiceRegistry",
	"resolve_service",
	"resolve_service_from_app",
	"SVMModelService",
	"svm_model_service",
]
=======
# Use refactored biometric implementation to avoid legacy indentation issues
from app.services.biometric import BiometricService

from app.services.api_key_service import APIKeyService

__all__ = ["AuthService", "BiometricService", "APIKeyService"]
>>>>>>> chaizaa/habib_api
