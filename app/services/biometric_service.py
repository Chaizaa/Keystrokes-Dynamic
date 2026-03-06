"""BiometricService (ML-only).

Historically this project had a similarity-based BiometricService.
As of March 2026, the requested behaviour is to use ONLY ML (RandomForest
per-user) with EER-based thresholds (as in `ml/ml_pta.py`).

This service keeps the same public method names used by routes (`get_enrollment_status`,
`verify_keystroke_sample`) but delegates verification to the DB-backed ML layer.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import func, select

from app.models import UsersVector, db
from app.services.ml_model_service import ml_model_service


class BiometricService:
    """ML-only biometric service (keeps legacy method names)."""

    # Keep these to maintain existing UX expectations in the UI
    MIN_SAMPLES_FOR_VERIFICATION = 3
    RECOMMENDED_SAMPLES = 100

    # Legacy confidence thresholds (kept for compatibility/tests; not used by ML-only flow)
    EXACT_MATCH_THRESHOLD = 0.95
    HIGH_CONFIDENCE_THRESHOLD = 0.85
    MEDIUM_CONFIDENCE_THRESHOLD = 0.70
    LOW_CONFIDENCE_THRESHOLD = 0.55

    def __init__(self, db: Optional[object] = None):
        # `db` was previously the legacy Database() manager.
        # It is kept only for backwards compatibility; ML paths use SQLAlchemy.
        self.db = db

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
        if not username:
            return {
                "count": 0,
                "enrolled": False,
                "ready_for_login": False,
                "minimum_samples": self.MIN_SAMPLES_FOR_VERIFICATION,
                "recommended_samples": self.RECOMMENDED_SAMPLES,
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
            "enrolled": count >= self.MIN_SAMPLES_FOR_VERIFICATION,
            "ready_for_login": count >= self.RECOMMENDED_SAMPLES,
            "minimum_samples": self.MIN_SAMPLES_FOR_VERIFICATION,
            "recommended_samples": self.RECOMMENDED_SAMPLES,
        }

    def train_user_model(self, username: str, *, force: bool = False) -> Dict[str, Any]:
        """Train and persist the per-user ML model (ml_pta style)."""
        res = ml_model_service.train_user_model(username, force=force)
        return {
            "success": bool(res.success),
            "reason": res.reason,
            "message": res.message,
            "model_id": res.model_id,
            "threshold": res.threshold,
            "eer": res.eer,
            "metrics": res.metrics,
        }

    def verify_keystroke_sample(self, arg1, arg2=None, use_statistical: bool = True) -> Dict[str, Any]:
        """Verify a keystroke sample using ML only.

        Supported call styles (kept for backwards compatibility):
        - (username: str, features: dict)
        - (features: dict, _ignored_templates: list)
        """
        if isinstance(arg1, str):
            username = arg1
            features = arg2 or {}
        else:
            features = arg1 or {}
            username = (features or {}).get("username")

        username = (username or "").strip()
        if not username:
            return {
                "success": False,
                "verified": False,
                "score": 0.0,
                "reason": "missing_username",
                "message": "Missing username",
            }

        # Attempt auto-train if the user has no stored model.
        if ml_model_service.get_model_row(username) is None:
            train_res = ml_model_service.train_user_model(username, force=False)
            if not train_res.success:
                return {
                    "success": False,
                    "verified": False,
                    "score": 0.0,
                    "reason": "model_not_found",
                    "message": (
                        train_res.message
                        or "Model not available yet; please complete enrollment/training"
                    ),
                    "train_reason": train_res.reason,
                }

        pred = ml_model_service.verify(username, features)
        if not pred.get("success"):
            return {
                "success": False,
                "verified": False,
                "score": 0.0,
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
            "method": "random_forest",
            "model_id": pred.get("model_id"),
            "message": "Biometric verification successful" if pred.get("verified") else "Biometric verification failed",
        }
