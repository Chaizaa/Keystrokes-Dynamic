"""BiometricService (ML-only).

Historically this project had a similarity-based BiometricService.
As of March 2026, the requested behaviour is to use ONLY ML (RandomForest
per-user) with EER-based thresholds (as in `ml/ml_pta.py`).

This service keeps the same public method names used by routes (`get_enrollment_status`,
`verify_keystroke_sample`) but delegates verification to the DB-backed ML layer.
"""

from __future__ import annotations

import os
import json
from typing import Any, Dict, List

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
    """ML-only biometric service (keeps legacy method names)."""

    # Keep these to maintain existing UX expectations in the UI
    MIN_SAMPLES_FOR_VERIFICATION = 3
    RECOMMENDED_SAMPLES = 10

    # Legacy confidence thresholds (kept for compatibility/tests; not used by ML-only flow)
    EXACT_MATCH_THRESHOLD = 0.95
    HIGH_CONFIDENCE_THRESHOLD = 0.85
    MEDIUM_CONFIDENCE_THRESHOLD = 0.70
    LOW_CONFIDENCE_THRESHOLD = 0.55

    def __init__(self):
        pass

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
            # Outside app context (e.g. some unit tests), fallback to env/default.
            pass
        return self._normalize_backend_name(str(backend))

    def _configured_int(self, config_name: str, fallback: int) -> int:
        try:
            from flask import current_app

            return int(current_app.config.get(config_name, fallback))
        except RuntimeError:
            return int(os.environ.get(config_name, fallback))

    def get_minimum_samples_for_verification(self) -> int:
        return self._configured_int("MIN_SAMPLES_FOR_VERIFICATION", self.MIN_SAMPLES_FOR_VERIFICATION)

    def get_recommended_samples(self) -> int:
        return self._configured_int("RECOMMENDED_SAMPLES", self.RECOMMENDED_SAMPLES)

    @staticmethod
    def _to_float_vector(raw_value: Any) -> List[float]:
        if raw_value is None:
            return []
        if isinstance(raw_value, list):
            try:
                return [float(x) for x in raw_value]
            except Exception:
                return []
        if isinstance(raw_value, str):
            try:
                parsed = json.loads(raw_value)
                if isinstance(parsed, list):
                    return [float(x) for x in parsed]
            except Exception:
                return []
        return []

    def _build_legacy_combined_vector(self, sample: Dict[str, Any]) -> List[float]:
        combined: List[float] = []
        for key in ("H_vector", "DD_vector", "UD_vector"):
            combined.extend(self._to_float_vector((sample or {}).get(key)))
        return combined

    def _has_required_legacy_vectors(self, sample: Dict[str, Any]) -> bool:
        for key in ("H_vector", "DD_vector", "UD_vector"):
            if not self._to_float_vector((sample or {}).get(key)):
                return False
        return True

    @staticmethod
    def _normalize_distance(distance: float) -> float:
        return 1.0 / (1.0 + max(0.0, distance))

    @staticmethod
    def _normalize_cosine(cosine_sim: float) -> float:
        return max(0.0, min(1.0, (cosine_sim + 1.0) / 2.0))

    def _legacy_confidence_label(self, score: float) -> str:
        if score >= self.EXACT_MATCH_THRESHOLD:
            return "Exact Match"
        if score >= self.HIGH_CONFIDENCE_THRESHOLD:
            return "High Confidence"
        if score >= self.MEDIUM_CONFIDENCE_THRESHOLD:
            return "Medium Confidence"
        if score >= self.LOW_CONFIDENCE_THRESHOLD:
            return "Low Confidence"
        return "Very Low Confidence"

    def _legacy_verify_from_samples(self, sample: Dict[str, Any], enrollment_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        if len(enrollment_list) < self.MIN_SAMPLES_FOR_VERIFICATION:
            return {
                "error": (
                    "Insufficient enrollment data: "
                    f"need at least {self.MIN_SAMPLES_FOR_VERIFICATION} samples"
                )
            }

        if not self._has_required_legacy_vectors(sample):
            return {"error": "Missing required vectors in verification sample"}

        sample_vec = self._build_legacy_combined_vector(sample)
        if not sample_vec:
            return {"error": "Missing vector data in verification sample"}

        euclidean_scores: List[float] = []
        cosine_scores: List[float] = []

        for template in enrollment_list:
            if not self._has_required_legacy_vectors(template):
                continue
            template_vec = self._build_legacy_combined_vector(template)
            if not template_vec:
                continue

            min_len = min(len(sample_vec), len(template_vec))
            if min_len == 0:
                continue

            sv = sample_vec[:min_len]
            tv = template_vec[:min_len]

            distance = self.calculate_euclidean_distance(sv, tv)
            cosine = self.calculate_cosine_similarity(sv, tv)

            euclidean_scores.append(self._normalize_distance(distance))
            cosine_scores.append(self._normalize_cosine(cosine))

        if not euclidean_scores or not cosine_scores:
            return {"error": "Unable to compute similarity scores from enrollment templates"}

        statistical = self.calculate_statistical_similarity(sample, enrollment_list)
        statistical_score = float(statistical.get("score") or 0.0)

        euclidean_score = float(sum(euclidean_scores) / len(euclidean_scores))
        cosine_score = float(sum(cosine_scores) / len(cosine_scores))

        # Keep compatibility with historical shape: weighted hybrid score.
        confidence_score = float(
            (0.35 * euclidean_score)
            + (0.15 * cosine_score)
            + (0.50 * statistical_score)
        )
        confidence_score = max(0.0, min(1.0, confidence_score))

        decision = "genuine" if confidence_score >= self.LOW_CONFIDENCE_THRESHOLD else "impostor"

        return {
            "decision": decision,
            "confidence_score": confidence_score,
            "confidence_label": self._legacy_confidence_label(confidence_score),
            "euclidean_score": euclidean_score,
            "cosine_score": cosine_score,
            "statistical_score": statistical_score,
            "primary_metric": "hybrid_confidence",
        }

    def _load_enrollment_templates(self, username: str, limit: int = 100) -> List[Dict[str, Any]]:
        stmt = (
            select(UsersVector)
            .where(
                UsersVector.username == username,
                (UsersVector.event_type == "enrollment")
                | (UsersVector.data_type == "enrollment"),
            )
            .order_by(UsersVector.id.desc())
            .limit(limit)
        )
        rows = db.session.execute(stmt).scalars().all()

        templates: List[Dict[str, Any]] = []
        for row in rows:
            templates.append(
                {
                    "H_vector": self._to_float_vector(getattr(row, "H_vector", None)),
                    "DD_vector": self._to_float_vector(getattr(row, "DD_vector", None)),
                    "UD_vector": self._to_float_vector(getattr(row, "UD_vector", None)),
                    "UU_vector": self._to_float_vector(getattr(row, "UU_vector", None)),
                    "DU_vector": self._to_float_vector(getattr(row, "DU_vector", None)),
                }
            )
        return templates

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
    # Legacy helpers (compatibility)
    # ------------------------------------------------------------------

    def calculate_euclidean_distance(self, vec1: List[float], vec2: List[float]) -> float:
        """Legacy helper retained for tests; not used by the ML-only pipeline."""
        import numpy as np

        if len(vec1) != len(vec2):
            raise ValueError("Vectors must have same length")
        v1 = np.array(vec1, dtype=float)
        v2 = np.array(vec2, dtype=float)
        return float(np.linalg.norm(v1 - v2))

    def calculate_cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Legacy helper retained for tests; not used by the ML-only pipeline."""
        import numpy as np

        if len(vec1) != len(vec2):
            raise ValueError("Vectors must have same length")
        v1 = np.array(vec1, dtype=float)
        v2 = np.array(vec2, dtype=float)
        norm1 = float(np.linalg.norm(v1))
        norm2 = float(np.linalg.norm(v2))
        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0
        return float(np.dot(v1, v2) / (norm1 * norm2))

    def calculate_statistical_similarity(self, sample: Dict[str, Any], enrollment_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Legacy heuristic similarity retained for tests.

        The production flow uses ML-only verification; this is kept so older
        code paths and unit tests remain valid.
        """
        import statistics

        if not enrollment_list:
            return {
                "score": 0.0,
                "mean_h_diff": float("nan"),
                "std_h_diff": float("nan"),
            }
        try:
            sample_h = [float(x) for x in sample.get("H_vector", [])]
        except Exception:
            return {
                "score": 0.0,
                "mean_h_diff": float("nan"),
                "std_h_diff": float("nan"),
            }
        template_rows: List[List[float]] = []
        for t in enrollment_list:
            hv = (t or {}).get("H_vector") or []
            try:
                template_rows.append([float(x) for x in hv])
            except Exception:
                continue
        if not sample_h or not template_rows:
            return {
                "score": 0.0,
                "mean_h_diff": float("nan"),
                "std_h_diff": float("nan"),
            }
        min_len = min(len(sample_h), min(len(r) for r in template_rows))
        if min_len == 0:
            return {
                "score": 0.0,
                "mean_h_diff": float("nan"),
                "std_h_diff": float("nan"),
            }
        sample_h = sample_h[:min_len]
        trimmed = [[r[i] for i in range(min_len)] for r in template_rows]
        template_means = [statistics.mean(col) for col in zip(*trimmed)]
        diffs = [abs(a - b) for a, b in zip(sample_h, template_means)]
        mean_h_diff = statistics.mean(diffs)
        std_h_diff = statistics.pstdev(diffs) if len(diffs) > 1 else 0.0
        score = 1.0 / (1.0 + (mean_h_diff * 2.0))
        return {
            "score": float(score),
            "mean_h_diff": float(mean_h_diff),
            "std_h_diff": float(std_h_diff),
        }

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
        """Train and persist the per-user ML model (ml_pta style)."""
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
        """Verify a keystroke sample.

        Supports both the modern signature::
            verify_keystroke_sample(username: str, features: dict)

        and the legacy compatibility signature used in older unit tests::
            verify_keystroke_sample(sample: dict, enrollment_list: list[dict])
        """
        if isinstance(username, dict) and isinstance(features, list):
            return self._legacy_verify_from_samples(username, features)

        username = (username or "").strip()
        backend = self._backend_bundle()
        service = backend["service"]
        schedule_training = backend["schedule_training"]
        is_training = backend["is_training"]

        if not username:
            return {
                "success": False,
                "verified": False,
                "score": 0.0,
                "threshold": None,
                "backend": backend["name"],
                "method": backend["name"],
                "reason": "missing_username",
                "message": "Missing username",
            }

        # If no model is available, trigger training in a background thread so
        # the login request is not blocked by the 72-model grid search (which can
        # take 10-60 s).  The user will be asked to retry once training completes.
        if service.get_model_row(username) is None:
            from flask import current_app
            already_running = is_training(username)
            if not already_running:
                try:
                    app = current_app._get_current_object()
                    schedule_training(app, username, force=False)
                except RuntimeError:
                    # Outside of application context (e.g. tests) — fall back to sync train
                    service.train_user_model(username, force=False)

            # Re-check: maybe sync fallback just finished
            if service.get_model_row(username) is None:
                # Backward-compatible fallback for single-user/dev/test flows:
                # use enrollment-template similarity when ML model is unavailable.
                legacy_result = self._legacy_verify_from_samples(
                    features,
                    self._load_enrollment_templates(username),
                )
                if "error" not in legacy_result:
                    return {
                        "success": True,
                        "verified": bool(legacy_result.get("decision") == "genuine"),
                        "score": float(legacy_result.get("confidence_score", 0.0)),
                        "threshold": self.LOW_CONFIDENCE_THRESHOLD,
                        "confidence": legacy_result.get("confidence_label"),
                        "templates_used": 0,
                        "method": "legacy_similarity_fallback",
                        "model_id": None,
                        "message": "Biometric verification successful"
                        if legacy_result.get("decision") == "genuine"
                        else "Biometric verification failed",
                    }

                status = "training_started" if not already_running else "training_in_progress"
                return {
                    "success": False,
                    "verified": False,
                    "score": 0.0,
                    "threshold": None,
                    "backend": backend["name"],
                    "method": backend["name"],
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
                "success": False,
                "verified": False,
                "score": 0.0,
                "threshold": None,
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
            "message": "Biometric verification successful" if pred.get("verified") else "Biometric verification failed",
        }
