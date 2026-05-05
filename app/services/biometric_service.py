"""BiometricService (ML-only).

As of March 2026 this project uses ONLY ML (RandomForest / SVM per-user)
with EER-based thresholds (as in `ml/ml_pta.py`).

The service keeps the same public method names used by routes:
  - get_enrollment_status(username)
  - train_user_model(username, *, force)
  - verify_keystroke_sample(username, features)
"""

from __future__ import annotations

import os
from typing import Any, Dict

from sqlalchemy import func, select

from app.models import UsersVector, db
from app.services.ml_model_service import (
    is_training_in_progress as rf_is_training_in_progress,
    ml_model_service,
    schedule_background_training as schedule_rf_background_training,
)
from app.services.svm_model_service import (
    is_training_in_progress as svm_is_training_in_progress,
    schedule_background_training as schedule_svm_background_training,
    svm_model_service,
)


class BiometricService:
    """ML-only biometric service."""

    MIN_SAMPLES_FOR_VERIFICATION = 3
    RECOMMENDED_SAMPLES = 30

    def __init__(self):
        pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_backend_name(raw_name: str) -> str:
        name = (raw_name or "rf").strip().lower()
        return "svm" if name == "svm" else "rf"

    def _active_backend_name(self) -> str:
        backend = os.environ.get("ML_BACKEND", "rf")
        try:
            from flask import current_app
            backend = current_app.config.get("ML_BACKEND", backend)
        except RuntimeError:
            pass
        return self._normalize_backend_name(str(backend))

    def _configured_int(self, config_name: str, fallback: int) -> int:
        try:
            from flask import current_app
            return int(current_app.config.get(config_name, fallback))
        except RuntimeError:
            return int(os.environ.get(config_name, fallback))

    def get_minimum_samples_for_verification(self) -> int:
        return self._configured_int(
            "MIN_SAMPLES_FOR_VERIFICATION", self.MIN_SAMPLES_FOR_VERIFICATION
        )

    def get_recommended_samples(self) -> int:
        return self._configured_int("RECOMMENDED_SAMPLES", self.RECOMMENDED_SAMPLES)

    def _backend_bundle(self) -> Dict[str, Any]:
        backend = self._active_backend_name()
        if backend == "svm":
            return {
                "name": "svm",
                "service": svm_model_service,
                "schedule_training": schedule_svm_background_training,
                "is_training": svm_is_training_in_progress,
            }
        return {
            "name": "rf",
            "service": ml_model_service,
            "schedule_training": schedule_rf_background_training,
            "is_training": rf_is_training_in_progress,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_enrollment_status(self, username: str) -> Dict[str, Any]:
        """Return enrollment sample counts and readiness flags."""
        username = (username or "").strip()
        minimum_samples = self.get_minimum_samples_for_verification()
        recommended_samples = self.get_recommended_samples()
        if not username:
            return {
                "count": 0,
                "enrolled": False,
                "ready_for_login": False,
                "minimum_samples": minimum_samples,
                "recommended_samples": recommended_samples,
            }

        stmt = (
            select(func.count())
            .select_from(UsersVector)
            .where(
                UsersVector.username == username,
                (UsersVector.event_type == "enrollment")
                | (UsersVector.data_type == "enrollment"),
            )
        )
        count = int(db.session.execute(stmt).scalar() or 0)
        return {
            "count": count,
            "enrolled": count >= minimum_samples,
            "ready_for_login": count >= recommended_samples,
            "minimum_samples": minimum_samples,
            "recommended_samples": recommended_samples,
        }

    def train_user_model(self, username: str, *, force: bool = False) -> Dict[str, Any]:
        """Train and persist the per-user ML model."""
        backend = self._backend_bundle()
        res = backend["service"].train_user_model(username, force=force)
        return {
            "success": bool(res.success),
            "reason": res.reason,
            "message": res.message,
            "model_id": res.model_id,
            "threshold": res.threshold,
            "eer": res.eer,
            "metrics": res.metrics,
            "backend": backend["name"],
        }

    def verify_keystroke_sample(self, username: str, features: dict) -> Dict[str, Any]:
        """Verify a keystroke sample against the user's ML model."""
        username = (username or "").strip()
        backend = self._backend_bundle()
        service = backend["service"]
        schedule_training = backend["schedule_training"]
        is_training = backend["is_training"]

        if not username:
            return {
                "success": False, "verified": False,
                "score": 0.0, "threshold": None,
                "backend": backend["name"], "method": backend["name"],
                "reason": "missing_username", "message": "Missing username",
            }

        # If no model exists, trigger background training and ask user to retry.
        if service.get_model_row(username) is None:
            from flask import current_app
            already_running = is_training(username)
            if not already_running:
                try:
                    app = current_app._get_current_object()
                    schedule_training(app, username, force=False)
                except RuntimeError:
                    service.train_user_model(username, force=False)

            if service.get_model_row(username) is None:
                status = "training_started" if not already_running else "training_in_progress"
                return {
                    "success": False, "verified": False,
                    "score": 0.0, "threshold": None,
                    "backend": backend["name"], "method": backend["name"],
                    "reason": status,
                    "message": (
                        "Model training has started. Please try again in a moment."
                        if not already_running
                        else "Model training is in progress. Please try again shortly."
                    ),
                }

        pred = service.verify(username, features)
        if not pred.get("success"):
            return {
                "success": False, "verified": False,
                "score": 0.0, "threshold": None,
                "backend": backend["name"],
                "method": pred.get("method") or backend["name"],
                "reason": pred.get("reason", "predict_failed"),
                "message": pred.get("error") or "Prediction failed",
            }

        return {
            "success": True,
            "verified": bool(pred.get("verified")),
            "score": float(pred.get("score") or 0.0),
            "threshold": pred.get("threshold"),
            "confidence": pred.get("confidence"),
            "templates_used": 0,
            "method": pred.get("method") or backend["name"],
            "model_id": pred.get("model_id"),
            "message": (
                "Biometric verification successful"
                if pred.get("verified")
                else "Biometric verification failed"
            ),
        }
