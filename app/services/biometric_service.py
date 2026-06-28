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
from typing import cast
from flask import Flask, current_app

from sqlalchemy import func, select

from app.models import UsersVector, db
# from app.services import RF
from app.services.RF import (
    is_training_in_progress as rf_is_training_in_progress,
    ml_model_service,
    schedule_background_training as schedule_rf_background_training,
)
# from app.services.ml_model_service import (
#     is_training_in_progress as rf_is_training_in_progress,
#     ml_model_service,
#     schedule_background_training as schedule_rf_background_training,
# )
# from app.services.svm_model_service import (
#     is_training_in_progress as svm_is_training_in_progress,
#     schedule_background_training as schedule_svm_background_training,
#     svm_model_service,
# )
from app.services.svm import (
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
        if name in ("statistical", "stat", "template"):
            return "statistical"
        if name == "svm":
            return "svm"
        return "rf"

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

    # ------------------------------------------------------------------
    # Template-distance scorer (backend 'statistical')
    # ------------------------------------------------------------------
    # Confidence thresholds untuk label kategorikal (mirror habib_api).
    _EXACT_MATCH_THRESHOLD = 0.95
    _HIGH_CONFIDENCE_THRESHOLD = 0.85
    _MEDIUM_CONFIDENCE_THRESHOLD = 0.70
    _LOW_CONFIDENCE_THRESHOLD = 0.55

    @staticmethod
    def _safe_parse_vector(raw_value) -> list:
        """Parse stored vector (JSON string atau list) jadi list of floats."""
        import json as _json
        if raw_value is None:
            return []
        if isinstance(raw_value, list):
            try:
                return [float(x) for x in raw_value]
            except (TypeError, ValueError):
                return []
        if isinstance(raw_value, str):
            try:
                parsed = _json.loads(raw_value)
                if isinstance(parsed, list):
                    return [float(x) for x in parsed]
            except (_json.JSONDecodeError, TypeError, ValueError):
                pass
        return []

    def _load_enrollment_templates(self, username: str) -> list:
        """Load enrollment templates (parsed vectors) untuk username."""
        rows = db.session.execute(
            select(UsersVector)
            .where(
                UsersVector.username == username,
                (UsersVector.event_type == "enrollment")
                | (UsersVector.data_type == "enrollment"),
            )
            .order_by(UsersVector.id.desc())
        ).scalars().all()

        templates = []
        for row in rows:
            h_vec = self._safe_parse_vector(getattr(row, "H_vector", None))
            dd_vec = self._safe_parse_vector(getattr(row, "DD_vector", None))
            if not h_vec or not dd_vec:
                continue
            templates.append({
                "H_vector": h_vec,
                "DD_vector": dd_vec,
                "UD_vector": self._safe_parse_vector(getattr(row, "UD_vector", None)),
            })
        return templates

    @staticmethod
    def _euclidean_distance(a: list, b: list) -> float:
        import numpy as _np
        return float(_np.linalg.norm(
            _np.asarray(a, dtype=float) - _np.asarray(b, dtype=float)
        ))

    @staticmethod
    def _cosine_similarity(a: list, b: list) -> float:
        import numpy as _np
        va = _np.asarray(a, dtype=float)
        vb = _np.asarray(b, dtype=float)
        na = float(_np.linalg.norm(va))
        nb = float(_np.linalg.norm(vb))
        if na == 0.0 or nb == 0.0:
            return 0.0
        return float(_np.dot(va, vb) / (na * nb))

    @staticmethod
    def _statistical_similarity(sample_h: list, templates: list) -> float:
        """Per-position absolute-diff score pada H_vector, scaled ke [0,1]."""
        import statistics as _stats
        template_rows = []
        for t in templates:
            hv = t.get("H_vector") or []
            try:
                template_rows.append([float(x) for x in hv])
            except (TypeError, ValueError):
                continue
        if not sample_h or not template_rows:
            return 0.0
        min_len = min(len(sample_h), min(len(r) for r in template_rows))
        if min_len == 0:
            return 0.0
        sample_trimmed = sample_h[:min_len]
        template_trimmed = [r[:min_len] for r in template_rows]
        template_means = [_stats.mean(col) for col in zip(*template_trimmed)]
        diffs = [abs(a - b) for a, b in zip(sample_trimmed, template_means)]
        mean_diff = _stats.mean(diffs)
        return float(1.0 / (1.0 + (mean_diff * 2.0)))

    @classmethod
    def _confidence_label(cls, score: float) -> str:
        if score >= cls._EXACT_MATCH_THRESHOLD:
            return "Exact Match"
        if score >= cls._HIGH_CONFIDENCE_THRESHOLD:
            return "High Confidence"
        if score >= cls._MEDIUM_CONFIDENCE_THRESHOLD:
            return "Medium Confidence"
        if score >= cls._LOW_CONFIDENCE_THRESHOLD:
            return "Low Confidence"
        return "Very Low Confidence"

    def _verify_via_template_distance(self, username: str, features: dict) -> Dict[str, Any]:
        """Verify menggunakan template-distance (euclidean + cosine + statistical).

        Tidak memerlukan training. Cocok untuk dataset kecil di mana model ML
        cenderung degenerate.
        """
        import numpy as _np

        min_samples = self.get_minimum_samples_for_verification()
        templates = self._load_enrollment_templates(username)

        if len(templates) < min_samples:
            return {
                "success": False, "verified": False,
                "score": 0.0, "threshold": self._MEDIUM_CONFIDENCE_THRESHOLD,
                "backend": "statistical", "method": "template_distance",
                "reason": "insufficient_samples",
                "message": (
                    f"Insufficient enrollment samples "
                    f"({len(templates)}/{min_samples})"
                ),
            }

        login_H = features.get("H_vector") or []
        login_DD = features.get("DD_vector") or []
        if not login_H or not login_DD:
            return {
                "success": False, "verified": False,
                "score": 0.0, "threshold": self._MEDIUM_CONFIDENCE_THRESHOLD,
                "backend": "statistical", "method": "template_distance",
                "reason": "invalid_features",
                "message": "Missing required keystroke vectors",
            }

        eu_scores, cos_scores = [], []
        for t in templates:
            tH = t.get("H_vector") or []
            tDD = t.get("DD_vector") or []
            if len(tH) != len(login_H) or len(tDD) != len(login_DD):
                continue
            eu = (
                1.0 / (1.0 + self._euclidean_distance(login_H, tH))
                + 1.0 / (1.0 + self._euclidean_distance(login_DD, tDD))
            ) / 2.0
            eu_scores.append(eu)
            cos = (
                ((self._cosine_similarity(login_H, tH) + 1.0) / 2.0)
                + ((self._cosine_similarity(login_DD, tDD) + 1.0) / 2.0)
            ) / 2.0
            cos_scores.append(cos)

        if not eu_scores:
            return {
                "success": False, "verified": False,
                "score": 0.0, "threshold": self._MEDIUM_CONFIDENCE_THRESHOLD,
                "backend": "statistical", "method": "template_distance",
                "reason": "length_mismatch",
                "message": "Sample length does not match any template",
            }

        eu_score = float(_np.mean(eu_scores))
        cos_score = float(_np.mean(cos_scores))
        stat_score = self._statistical_similarity(login_H, templates)

        # Weighted base + statistical calibration (mengurangi false positive)
        base = 0.5 * eu_score + 0.3 * cos_score + 0.2 * stat_score
        base = float(max(0.0, min(1.0, base)))
        calibrated = float(max(0.0, min(1.0, base * stat_score)))

        # Threshold dapat di-override via PARTNER_DECISION_THRESHOLD env var
        try:
            from flask import current_app
            threshold = float(current_app.config.get(
                "PARTNER_DECISION_THRESHOLD", self._MEDIUM_CONFIDENCE_THRESHOLD
            ))
        except RuntimeError:
            threshold = self._MEDIUM_CONFIDENCE_THRESHOLD

        verified = calibrated >= threshold
        label = self._confidence_label(calibrated)

        return {
            "success": True,
            "verified": bool(verified),
            "score": round(calibrated, 4),
            "threshold": round(threshold, 4),
            "confidence": label,
            "templates_used": len(eu_scores),
            "backend": "statistical",
            "method": "template_distance",
            "euclidean_score": round(eu_score, 4),
            "cosine_score": round(cos_score, 4),
            "statistical_score": round(stat_score, 4),
            "message": (
                "Biometric verification successful"
                if verified
                else "Biometric verification failed"
            ),
        }

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
        """Verify a keystroke sample against the user's biometric profile.

        Dispatches based on ``ML_BACKEND`` env var:
          - ``rf`` (default): RandomForest per-user model
          - ``svm``: SVM RBF per-user model with probability calibration
          - ``statistical``: template-distance scoring (euclidean + cosine +
            statistical), tanpa fase training.
        """
        username = (username or "").strip()
        active_backend = self._active_backend_name()

        if not username:
            return {
                "success": False, "verified": False,
                "score": 0.0, "threshold": None,
                "backend": active_backend, "method": active_backend,
                "reason": "missing_username", "message": "Missing username",
            }

        # Statistical backend → dispatch ke template-distance scorer.
        # Tidak membutuhkan training, langsung bandingkan dengan enrollment
        # vectors yang tersimpan di users_vectors.
        if active_backend == "statistical":
            return self._verify_via_template_distance(username, features)

        backend = self._backend_bundle()
        service = backend["service"]
        schedule_training = backend["schedule_training"]
        is_training = backend["is_training"]

        # If no model exists, trigger background training and ask user to retry.
        if service.get_model_row(username) is None:
            from flask import current_app
            from typing import Any
            already_running = is_training(username)
            if not already_running:
                try:
                    proxy: Any = current_app
                    app = proxy._get_current_object()

                    schedule_training(
                        app,
                        username,
                        force=False
                    )

                except RuntimeError:

                    service.train_user_model(
                        username,
                        force=False
                    )

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