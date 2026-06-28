"""ML model training + persistence service (RandomForest backend).

Implements the per-user one-vs-rest RandomForest approach:
- train/val split: 80/20 stratified (No testing split during enrollment)
- preprocessing: StandardScaler applied via Pipeline
- model selection: minimise EER on validation set
- threshold: the EER threshold on the validation set

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
from sqlalchemy import or_, select

from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
import skops.io as sio
import joblib

from app.models import User, UserMLModel, UsersVector, db
from app.services.base_model_service import (
    FEATURE_COLUMNS,
    BaseMLModelService,
    TrainResult,
    _compute_eer_threshold,
    _compute_metrics,
    _now_utc,
)


class MLModelService(BaseMLModelService):
    """Train, store, and use per-user RandomForest models via Pipeline."""

    MODEL_TYPE = "RandomForestClassifier"

    # Single-combination grid keeps per-user training under ~2s
    PARAM_GRID: Dict[str, List[Any]] = {
        "n_estimators": [100],
        "max_depth": [8, 10],
        "min_samples_leaf": [1, 2],
        "max_features": ["sqrt", "log2"]
    }

    def __init__(self):
        super().__init__()

    # ------------------------------------------------------------------
    # Backend-specific: deserialise + validate RandomForest Pipeline
    # ------------------------------------------------------------------
    def _deserialize_model(self, blob: bytes):
        """Deserialise and validate the model pipeline from BLOB."""

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

        # Mengizinkan Pipeline selain RandomForestClassifier murni
        if not isinstance(model, (RandomForestClassifier, Pipeline)):
            raise ValueError(
                f"Model must be RandomForestClassifier or Pipeline, got {type(model).__name__}"
            )
        if not hasattr(model, "predict_proba"):
            raise ValueError("Model must have predict_proba method")

        expected = len(FEATURE_COLUMNS)
        
        # Cek jumlah fitur, handle jika model dibungkus Pipeline
        # actual_features = getattr(model, "n_features_in_", None)
        # if actual_features is None and hasattr(model, "steps"):
        #     actual_features = getattr(model.steps[0][1], "n_features_in_", None)
        actual_features = getattr(model, "n_features_in_", None)

        if actual_features is None and isinstance(model, Pipeline):
            actual_features = getattr(
                model.steps[0][1],
                "n_features_in_",
                None
            )

        if actual_features is not None and actual_features != expected:
            raise ValueError(
                f"Feature count mismatch: expected {expected}, got {actual_features}"
            )
            
        return model

    # ------------------------------------------------------------------
    # Train
    # ------------------------------------------------------------------
    def train_user_model(self, username: str, *, force: bool = False) -> TrainResult:
        """Train (or retrain) a user RandomForest model using 80/20 split."""
        username = (username or "").strip()
        if not username:
            return TrainResult(success=False, username="", reason="missing_username")

        user = db.session.execute(select(User).where(User.username == username)).scalars().one_or_none()
        if not user:
            return TrainResult(
                success=False, username=username,
                reason="user_not_found", message="User not found",
            )

        # if (not force) and self.get_model_row(username):
        #     row = self.get_model_row(username)
        #     return TrainResult(
        #         success=True, username=username,
        #         threshold=float(row.threshold), model_id=int(row.id),
        #         reason="already_trained", message="Model already exists",
        #     )
        row = self.get_model_row(username)

        if (not force) and row:
            return TrainResult(
                success=True,
                username=username,
                threshold=float(row.threshold),
                model_id=int(row.id),
                reason="already_trained",
                message="Model already exists",
            )

        rows = self._load_training_rows()
        X_all, y_all = self._rows_to_xy(rows, username)

        if X_all.shape[0] == 0:
            return TrainResult(
                success=False, username=username,
                reason="no_training_rows",
                message="No enrollment rows found for training",
            )

        n_genuine = int(np.sum(y_all == 1))
        n_impostor = int(np.sum(y_all == 0))

        if n_genuine < 2:
            return TrainResult(
                success=False, username=username,
                reason="insufficient_class_balance",
                message=f"Not enough genuine samples: genuine={n_genuine}",
            )

        X_all, y_all = self._ensure_class_balance(X_all, y_all)
        n_genuine = int(np.sum(y_all == 1))
        n_impostor = int(np.sum(y_all == 0))

        try:
            # Mengubah split menjadi 80% Train, 20% Validation
            X_train, X_val, y_train, y_val = train_test_split(
                X_all, y_all, test_size=0.2, stratify=y_all, random_state=42,
            )
        except Exception as exc:
            return TrainResult(
                success=False, username=username,
                reason="split_failed", message=str(exc),
            )

        best_pipeline = None
        best_eer = 1.0
        best_threshold = None
        best_params: Dict[str, Any] = {}

        for n in self.PARAM_GRID["n_estimators"]:
            for depth in self.PARAM_GRID["max_depth"]:
                for leaf in self.PARAM_GRID["min_samples_leaf"]:
                    for feat in self.PARAM_GRID["max_features"]:
                        
                        # Bungkus Scaler dan RandomForest dalam satu Pipeline
                        pipeline = Pipeline([
                            ('scaler', StandardScaler()),
                            ('rf', RandomForestClassifier(
                                n_estimators=n, max_depth=depth,
                                min_samples_leaf=leaf, max_features=feat,
                                class_weight="balanced", random_state=42, n_jobs=-1,
                            ))
                        ])
                        
                        # Fit pipeline (otomatis fit_transform scaler, lalu fit model)
                        pipeline.fit(X_train, y_train)
                        
                        # Evaluasi di data validasi (otomatis di-transform oleh scaler)
                        val_probs = pipeline.predict_proba(X_val)[:, 1]
                        eer, thr = _compute_eer_threshold(y_val, val_probs)
                        
                        if eer < best_eer:
                            best_eer = float(eer)
                            best_threshold = float(thr)
                            best_pipeline = pipeline
                            best_params = {
                                "n_estimators": n, "max_depth": depth,
                                "min_samples_leaf": leaf, "max_features": feat,
                                "random_state": 42, "class_weight": "balanced",
                            }

        if best_pipeline is None or best_threshold is None:
            return TrainResult(
                success=False, username=username,
                reason="training_failed", message="Unable to select a best model",
            )

        # Hitung metrik akhir menggunakan data validasi
        val_probs_final = best_pipeline.predict_proba(X_val)[:, 1]
        val_metrics = _compute_metrics(y_val, val_probs_final, best_threshold)
        
        metrics = {
            "best_eer_val": best_eer,
            "threshold": best_threshold,
            "validation": {**val_metrics, "EER": float(best_eer)},
        }

        # Serialize seluruh pipeline (model + scaler tersimpan sekaligus)
        blob = self._serialize_model(best_pipeline)

        row = self.get_model_row_any(username)
        if row is None:
            row = UserMLModel(
                user_id=user.id, username=username,
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
            row.user_id = user.id
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
            reason="trained", message="Model trained successfully",
        )

    # ------------------------------------------------------------------
    # Verify
    # ------------------------------------------------------------------
    def verify(self, username: str, features: Dict[str, Any]) -> Dict[str, Any]:
        """Predict probability and apply per-user EER threshold."""
        username = (username or "").strip()
        if not username:
            return {"success": False, "verified": False, "reason": "missing_username"}

        row = self.get_model_row(username)
        if row is None:
            return {"success": False, "verified": False, "reason": "model_not_found"}

        try:
            model_pipeline, feature_names = self._get_cached_runtime(row)
            X = self._build_feature_vector(features, feature_names)
            
            # X otomatis masuk ke StandardScaler lalu ke RandomForest
            prob = float(model_pipeline.predict_proba(X)[0, 1])
            threshold = float(row.threshold)
            
            return {
                "success": True,
                "verified": bool(prob >= threshold),
                "score": round(prob, 4),
                "threshold": round(threshold, 4),
                "confidence": self._confidence_label(prob, threshold),
                "model_id": int(row.id),
                "method": "random_forest",
            }
        except Exception as exc:
            return {
                "success": False, "verified": False,
                "reason": "predict_failed", "error": str(exc),
            }

# ---------------------------------------------------------------------------
# Module-level singleton + background training helpers
# (Tidak ada perubahan pada bagian ini)
# ---------------------------------------------------------------------------
ml_model_service = MLModelService()

_training_in_progress: set = set()
_training_lock = threading.Lock()

def schedule_background_training(app, username: str, *, force: bool = False) -> bool:
    """Kick off model training for *username* in a background daemon thread."""
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
                ml_model_service.train_user_model(username, force=force)
        except Exception as exc:
            print(f"[BG-TRAIN] Error training model for {username}: {exc}")
        finally:
            with _training_lock:
                _training_in_progress.discard(username)

    t = threading.Thread(target=_run, daemon=True, name=f"ml-train-{username}")
    t.start()
    return True

def is_training_in_progress(username: str) -> bool:
    """Return True if a background training thread is active for *username*."""
    with _training_lock:
        return username in _training_in_progress