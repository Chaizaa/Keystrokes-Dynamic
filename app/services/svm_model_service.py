"""SVM model training + persistence service.

Implements per-user one-vs-rest SVM verification with probability output
(`SVC(probability=True)`) so scores remain compatible with existing response
shape and thresholding logic.

All shared logic (serialisation, CRUD, dataset building, caching) lives in
:mod:`app.services.base_model_service`.
"""

from __future__ import annotations

import io
import json
import threading
import zipfile
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from sqlalchemy import select

from app.models import User, UserMLModel, UsersVector, db
from app.services.base_model_service import (
    FEATURE_COLUMNS,
    BaseMLModelService,
    TrainResult,
    _compute_eer_threshold,
    _compute_metrics,
    _now_utc,
)


class SVMModelService(BaseMLModelService):
    """Train, store, and use per-user SVM models."""

    MODEL_TYPE = "SVC_RBF_probability"

    PARAM_GRID: Dict[str, List[Any]] = {
        "C": [1.0, 10.0, 50.0],
        "gamma": ["scale", "auto"],
    }

    # Keep impostor pool quality conservative (complete users only).
    MIN_REQUIRED_ENROLLMENT_ROWS = 10

    def __init__(self):
        super().__init__()

    # ------------------------------------------------------------------
    # Backend-specific: CRUD — strict model_type match for SVM
    # ------------------------------------------------------------------
    def get_model_row(self, username: str) -> Optional[UserMLModel]:
        if not username:
            return None
        return (
            db.session.execute(
                select(UserMLModel)
                .where(UserMLModel.username == username)
                .where(UserMLModel.model_type == self.MODEL_TYPE)
            )
            .scalars()
            .one_or_none()
        )

    # ------------------------------------------------------------------
    # Backend-specific: deserialise + validate SVM Pipeline
    # ------------------------------------------------------------------
    def _deserialize_model(self, blob: bytes):
        """Deserialise and validate the SVM pipeline from BLOB."""
        from sklearn.pipeline import Pipeline
        from sklearn.svm import SVC
        import skops.io as sio
        import joblib

        if not isinstance(blob, bytes) or len(blob) == 0:
            raise ValueError("Model blob is empty or invalid")

        try:
            buf = io.BytesIO(blob)
            untrusted = sio.get_untrusted_types(file=buf)
            model = sio.load(buf, trusted=untrusted)
        except zipfile.BadZipFile:
            buf = io.BytesIO(blob)
            model = joblib.load(buf)
        except Exception as e:
            raise ValueError(f"Failed to deserialise model: {e}")

        if isinstance(model, Pipeline):
            svc = model.named_steps.get("svc")
            if not isinstance(svc, SVC):
                raise ValueError("Pipeline must contain an SVC step named 'svc'")
            if not getattr(svc, "probability", False):
                raise ValueError("SVC model must be trained with probability=True")
        elif isinstance(model, SVC):
            if not getattr(model, "probability", False):
                raise ValueError("SVC model must be trained with probability=True")
        else:
            raise ValueError(f"Model must be Pipeline/SVC, got {type(model).__name__}")

        if not hasattr(model, "predict_proba"):
            raise ValueError("Model must have predict_proba method")

        expected = len(FEATURE_COLUMNS)
        n_features = getattr(model, "n_features_in_", None)
        if n_features is None and isinstance(model, Pipeline):
            svc = model.named_steps.get("svc")
            n_features = getattr(svc, "n_features_in_", None)
        if n_features is None:
            raise ValueError("Model missing n_features_in_ attribute")
        if int(n_features) != expected:
            raise ValueError(
                f"Feature count mismatch: expected {expected}, got {int(n_features)}"
            )
        return model

    # ------------------------------------------------------------------
    # Dataset helpers (SVM-specific: filter complete users for impostor pool)
    # ------------------------------------------------------------------
    def _filter_complete_user_rows(
        self, rows: List[UsersVector], target_username: str
    ) -> List[UsersVector]:
        counts: Dict[str, int] = {}
        for r in rows:
            uname = getattr(r, "username", None)
            if not uname:
                continue
            counts[uname] = counts.get(uname, 0) + 1

        allowed = {
            uname for uname, cnt in counts.items()
            if cnt >= self.MIN_REQUIRED_ENROLLMENT_ROWS
        }
        allowed.add(target_username)
        return [r for r in rows if getattr(r, "username", None) in allowed]

    # ------------------------------------------------------------------
    # Train
    # ------------------------------------------------------------------
    def train_user_model(self, username: str, *, force: bool = False) -> TrainResult:
        username = (username or "").strip()
        if not username:
            return TrainResult(success=False, username="", reason="missing_username")

        user = db.session.execute(select(User).where(User.username == username)).scalars().one_or_none()
        if not user:
            return TrainResult(
                success=False, username=username,
                reason="user_not_found", message="User not found",
            )

        existing = self.get_model_row(username)
        if (not force) and existing:
            return TrainResult(
                success=True, username=username,
                threshold=float(existing.threshold), model_id=int(existing.id),
                reason="already_trained", message="SVM model already exists",
            )

        rows = self._load_training_rows()
        filtered = self._filter_complete_user_rows(rows, username)
        X_all, y_all = self._rows_to_xy(filtered, username)

        # Fallback: if conservative pool is too small, use full corpus
        if X_all.shape[0] == 0 or int(np.sum(y_all == 0)) < 2:
            fallback_X, fallback_y = self._rows_to_xy(rows, username)
            if fallback_X.shape[0] > X_all.shape[0]:
                X_all, y_all = fallback_X, fallback_y

        if X_all.shape[0] == 0:
            return TrainResult(
                success=False, username=username,
                reason="no_training_rows",
                message="No enrollment rows found for training",
            )

        n_genuine = int(np.sum(y_all == 1))
        n_impostor = int(np.sum(y_all == 0))
        if n_genuine < 2 or n_impostor < 2:
            return TrainResult(
                success=False, username=username,
                reason="insufficient_class_balance",
                message=(
                    "Not enough data for one-vs-rest model. "
                    f"genuine={n_genuine}, impostor={n_impostor}"
                ),
            )

        from sklearn.model_selection import train_test_split
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
        from sklearn.svm import SVC

        try:
            X_train, X_temp, y_train, y_temp = train_test_split(
                X_all, y_all, test_size=0.4, stratify=y_all, random_state=42,
            )
            X_val, X_test, y_val, y_test = train_test_split(
                X_temp, y_temp, test_size=0.5, stratify=y_temp, random_state=42,
            )
        except Exception as exc:
            return TrainResult(
                success=False, username=username,
                reason="split_failed", message=str(exc),
            )

        best_model = None
        best_eer = 1.0
        best_threshold = None
        best_params: Dict[str, Any] = {}

        for c_val in self.PARAM_GRID["C"]:
            for gamma in self.PARAM_GRID["gamma"]:
                model = Pipeline([
                    ("scaler", StandardScaler()),
                    ("svc", SVC(
                        kernel="rbf", C=c_val, gamma=gamma,
                        class_weight="balanced", probability=True, random_state=42,
                    )),
                ])
                model.fit(X_train, y_train)
                val_probs = model.predict_proba(X_val)[:, 1]
                eer, thr = _compute_eer_threshold(y_val, val_probs)
                if eer < best_eer:
                    best_eer = float(eer)
                    best_threshold = float(thr)
                    best_model = model
                    best_params = {
                        "kernel": "rbf", "C": c_val, "gamma": gamma,
                        "class_weight": "balanced",
                        "probability": True, "random_state": 42,
                    }

        if best_model is None or best_threshold is None:
            return TrainResult(
                success=False, username=username,
                reason="training_failed", message="Unable to select a best SVM model",
            )

        test_probs = best_model.predict_proba(X_test)[:, 1]
        test_metrics = _compute_metrics(y_test, test_probs, best_threshold)
        test_eer, _ = _compute_eer_threshold(y_test, test_probs)
        metrics = {
            "best_eer_val": best_eer,
            "threshold": best_threshold,
            "test": {**test_metrics, "EER": float(test_eer)},
            "impostor_filter_min_enrollment_rows": self.MIN_REQUIRED_ENROLLMENT_ROWS,
        }

        blob = self._serialize_model(best_model)

        row = self.get_model_row_any(username)
        if row is None:
            row = UserMLModel(
                user_id=int(user.id), username=username,
                model_blob=blob, threshold=float(best_threshold),
                feature_names_json=json.dumps(FEATURE_COLUMNS),
                model_type=self.MODEL_TYPE, sklearn_version=None,
                metrics_json=json.dumps(metrics),
                train_params_json=json.dumps(best_params),
                n_samples_total=int(X_all.shape[0]),
                n_genuine=n_genuine, n_impostor=n_impostor,
                created_at=_now_utc(), updated_at=_now_utc(),
            )
            db.session.add(row)
        else:
            row.user_id = int(user.id)
            row.model_blob = blob
            row.threshold = float(best_threshold)
            row.feature_names_json = json.dumps(FEATURE_COLUMNS)
            row.model_type = self.MODEL_TYPE
            row.metrics_json = json.dumps(metrics)
            row.train_params_json = json.dumps(best_params)
            row.n_samples_total = int(X_all.shape[0])
            row.n_genuine = n_genuine
            row.n_impostor = n_impostor
            row.updated_at = _now_utc()

        db.session.commit()
        self._invalidate_user_runtime_cache(username)
        return TrainResult(
            success=True, username=username,
            threshold=float(best_threshold), eer=float(best_eer),
            metrics=metrics, model_id=int(row.id),
            reason="trained", message="SVM model trained successfully",
        )

    # ------------------------------------------------------------------
    # Verify
    # ------------------------------------------------------------------
    def verify(self, username: str, features: Dict[str, Any]) -> Dict[str, Any]:
        username = (username or "").strip()
        if not username:
            return {"success": False, "verified": False, "reason": "missing_username"}

        row = self.get_model_row(username)
        if row is None:
            return {"success": False, "verified": False, "reason": "model_not_found"}

        try:
            model, feature_names = self._get_cached_runtime(row)
            X = self._build_feature_vector(features, feature_names)
            prob = float(model.predict_proba(X)[0, 1])
            threshold = float(row.threshold)
            return {
                "success": True,
                "verified": bool(prob >= threshold),
                "score": round(prob, 4),
                "threshold": round(threshold, 4),
                "confidence": self._confidence_label(prob, threshold),
                "model_id": int(row.id),
                "method": "svm_rbf_probability",
            }
        except Exception as exc:
            return {
                "success": False, "verified": False,
                "reason": "predict_failed", "error": str(exc),
            }


# ---------------------------------------------------------------------------
# Module-level singleton + background training helpers
# ---------------------------------------------------------------------------
svm_model_service = SVMModelService()

_training_in_progress: set = set()
_training_lock = threading.Lock()


def schedule_background_training(app, username: str, *, force: bool = False) -> bool:
    username = (username or "").strip()
    if not username:
        return False

    with _training_lock:
        if username in _training_in_progress:
            return False
        _training_in_progress.add(username)

    def _run():
        try:
            with app.app_context():
                svm_model_service.train_user_model(username, force=force)
        except Exception as exc:
            print(f"[SVM-BG-TRAIN] Error training model for {username}: {exc}")
        finally:
            with _training_lock:
                _training_in_progress.discard(username)

    t = threading.Thread(target=_run, daemon=True, name=f"svm-train-{username}")
    t.start()
    return True


def is_training_in_progress(username: str) -> bool:
    with _training_lock:
        return username in _training_in_progress
