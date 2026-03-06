"""ML-based keystroke verification (RandomForest per-user).

Requested behaviour (March 2026):
- Training & threshold selection must follow `ml/ml_pta.py`.
- No default threshold values: each user must have their own EER-based threshold.
- Model artifacts are stored in the application DB (table `user_ml_models`).
- If a user has no model after enrollment, the system should train it automatically.

This module is a thin wrapper around :mod:`app.services.ml_model_service`.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from app.services.ml_model_service import ml_model_service


class MLKeystrokeVerifier:
    """Verify a login sample using a per-user RandomForest model."""

    def __init__(
        self,
        *,
        enabled: Optional[bool] = None,
        auto_train: Optional[bool] = None,
    ) -> None:
        # Default ON: the app is configured to rely on ML-only verification.
        self.enabled = (
            enabled
            if enabled is not None
            else os.environ.get("ML_VERIFY_ENABLED", "true").lower() == "true"
        )
        self.auto_train = (
            auto_train
            if auto_train is not None
            else os.environ.get("ML_AUTO_TRAIN", "true").lower() == "true"
        )

    def verify(self, username: str, features: Dict[str, Any]) -> Dict[str, Any]:
        """Verify a login attempt.

        Returns a dict that matches the shape used by `/api/login`.
        If ML is disabled/unavailable, returns {available: False}.
        """

        if not self.enabled:
            return {
                "available": False,
                "success": False,
                "verified": False,
                "reason": "ml_disabled",
            }

        if not username:
            return {
                "available": False,
                "success": False,
                "verified": False,
                "reason": "missing_username",
            }

        # Ensure model exists (optionally train)
        if ml_model_service.get_model_row(username) is None and self.auto_train:
            train_res = ml_model_service.train_user_model(username, force=False)
            if not train_res.success:
                return {
                    "available": False,
                    "success": False,
                    "verified": False,
                    "reason": "auto_train_failed",
                    "train_reason": train_res.reason,
                    "message": train_res.message,
                }

        pred = ml_model_service.verify(username, features)
        if not pred.get("success"):
            return {
                "available": False,
                "success": False,
                "verified": False,
                "reason": pred.get("reason", "ml_error"),
                "error": pred.get("error"),
            }

        return {
            "available": True,
            "success": True,
            "verified": bool(pred.get("verified")),
            "score": pred.get("score"),
            "threshold": pred.get("threshold"),
            "confidence": pred.get("confidence"),
            "templates_used": 0,
            "method": "random_forest",
            "model_id": pred.get("model_id"),
        }
