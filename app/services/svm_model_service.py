"""SVM model training + persistence service.

Implements per-user one-vs-rest SVM verification with probability output
(`SVC(probability=True)`) so scores remain compatible with existing response
shape and thresholding logic.
"""

from __future__ import annotations

import io
import json
import threading
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

from app.models import User, UserMLModel, UsersVector, db
from app.services.ml_model_service import FEATURE_COLUMNS


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _compute_metrics(y_true: np.ndarray, probs: np.ndarray, threshold: float) -> Dict[str, float]:
    from sklearn.metrics import confusion_matrix

    y_pred = (probs >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    accuracy = (tp + tn) / (tp + tn + fp + fn)
    far = fp / (fp + tn) if (fp + tn) != 0 else 0.0
    frr = fn / (fn + tp) if (fn + tp) != 0 else 0.0

    return {
        "TP": float(tp),
        "TN": float(tn),
        "FP": float(fp),
        "FN": float(fn),
        "accuracy": float(accuracy),
        "FAR": float(far),
        "FRR": float(frr),
    }


def _compute_eer_threshold(y_true: np.ndarray, probs: np.ndarray) -> Tuple[float, float]:
    from sklearn.metrics import roc_curve

    fpr, tpr, thresholds = roc_curve(y_true, probs)
    fnr = 1.0 - tpr
    idx = int(np.argmin(np.abs(fpr - fnr)))
    eer = float((fpr[idx] + fnr[idx]) / 2.0)
    threshold = float(thresholds[idx])
    return eer, threshold


@dataclass
class TrainResult:
    success: bool
    username: str
    threshold: Optional[float] = None
    eer: Optional[float] = None
    metrics: Optional[Dict[str, Any]] = None
    model_id: Optional[int] = None
    reason: Optional[str] = None
    message: Optional[str] = None


class SVMModelService:
    """Train, store, and use per-user SVM models."""

    MODEL_TYPE = "SVC_RBF_probability"

    # Conservative grid for phase-2 rollout.
    PARAM_GRID: Dict[str, List[Any]] = {
        "C": [1.0, 10.0, 50.0],
        "gamma": ["scale", "auto"],
    }

    # Keep impostor pool quality conservative (complete users only).
    MIN_REQUIRED_ENROLLMENT_ROWS = 100

    # In-process runtime cache to avoid repeated BLOB deserialization
    # on frequent login attempts for the same user/model revision.
    MODEL_CACHE_MAX_SIZE = 128

    def __init__(self):
        self._runtime_cache: "OrderedDict[Tuple[str, int, str], Tuple[Any, List[str]]]" = OrderedDict()
        self._runtime_cache_lock = threading.Lock()

    @staticmethod
    def _updated_marker(updated_at: Any) -> str:
        if updated_at is None:
            return "none"
        try:
            return updated_at.isoformat()
        except Exception:
            return str(updated_at)

    def _cache_key_from_row(self, row: UserMLModel) -> Tuple[str, int, str]:
        return (
            str(getattr(row, "username", "") or ""),
            int(getattr(row, "id", 0) or 0),
            self._updated_marker(getattr(row, "updated_at", None)),
        )

    def _invalidate_user_runtime_cache(self, username: str) -> None:
        username = (username or "").strip()
        if not username:
            return
        with self._runtime_cache_lock:
            stale_keys = [key for key in self._runtime_cache.keys() if key[0] == username]
            for key in stale_keys:
                self._runtime_cache.pop(key, None)

    def _get_cached_runtime(self, row: UserMLModel) -> Tuple[Any, List[str]]:
        key = self._cache_key_from_row(row)
        with self._runtime_cache_lock:
            cached = self._runtime_cache.get(key)
            if cached is not None:
                self._runtime_cache.move_to_end(key)
                return cached

        model = self._deserialize_model(row.model_blob)
        try:
            feature_names = json.loads(row.feature_names_json)
        except Exception:
            feature_names = FEATURE_COLUMNS

        if not isinstance(feature_names, list) or not feature_names:
            feature_names = FEATURE_COLUMNS

        payload = (model, feature_names)
        with self._runtime_cache_lock:
            self._runtime_cache[key] = payload
            self._runtime_cache.move_to_end(key)
            while len(self._runtime_cache) > self.MODEL_CACHE_MAX_SIZE:
                self._runtime_cache.popitem(last=False)
        return payload

    def get_model_row(self, username: str) -> Optional[UserMLModel]:
        if not username:
            return None
        return (
            db.session.query(UserMLModel)
            .filter(UserMLModel.username == username)
            .filter(UserMLModel.model_type == self.MODEL_TYPE)
            .one_or_none()
        )

    def get_model_row_any(self, username: str) -> Optional[UserMLModel]:
        if not username:
            return None
        return (
            db.session.query(UserMLModel)
            .filter(UserMLModel.username == username)
            .one_or_none()
        )

    def delete_model(self, username: str) -> bool:
        row = self.get_model_row(username)
        if not row:
            return False
        cached_username = (row.username or username or "").strip()
        db.session.delete(row)
        db.session.commit()
        self._invalidate_user_runtime_cache(cached_username)
        return True

    def _serialize_model(self, model) -> bytes:
        import joblib

        buf = io.BytesIO()
        joblib.dump(model, buf)
        return buf.getvalue()

    def _deserialize_model(self, blob: bytes):
        from sklearn.pipeline import Pipeline
        from sklearn.svm import SVC
        import joblib

        if not isinstance(blob, bytes) or len(blob) == 0:
            raise ValueError("Model blob is empty or invalid")

        try:
            buf = io.BytesIO(blob)
            model = joblib.load(buf)
        except Exception as e:
            raise ValueError(f"Failed to deserialize model: {e}")

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

        expected_features = len(FEATURE_COLUMNS)
        n_features = getattr(model, "n_features_in_", None)
        if n_features is None and isinstance(model, Pipeline):
            svc = model.named_steps.get("svc")
            n_features = getattr(svc, "n_features_in_", None)
        if n_features is None:
            raise ValueError("Model missing n_features_in_ attribute")
        if int(n_features) != expected_features:
            raise ValueError(
                f"Feature count mismatch: expected {expected_features}, got {int(n_features)}"
            )

        return model

    def _load_training_rows(self) -> List[UsersVector]:
        return (
            db.session.query(UsersVector)
            .filter(
                (UsersVector.event_type == "enrollment")
                | (UsersVector.data_type == "enrollment")
            )
            .all()
        )

    def _filter_complete_user_rows(self, rows: Iterable[UsersVector], target_username: str) -> List[UsersVector]:
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

    def _rows_to_xy(self, rows: Iterable[UsersVector], target_username: str) -> Tuple[np.ndarray, np.ndarray]:
        X_list: List[List[float]] = []
        y_list: List[int] = []

        for r in rows:
            uname = getattr(r, "username", None)
            if not uname:
                continue

            feat_row: List[float] = []
            missing = False
            for col in FEATURE_COLUMNS:
                val = getattr(r, col, None)
                if val is None:
                    missing = True
                    break
                try:
                    feat_row.append(float(val))
                except Exception:
                    missing = True
                    break
            if missing:
                continue

            X_list.append(feat_row)
            y_list.append(1 if uname == target_username else 0)

        if not X_list:
            return np.zeros((0, len(FEATURE_COLUMNS)), dtype=float), np.zeros((0,), dtype=int)

        X = np.asarray(X_list, dtype=float)
        y = np.asarray(y_list, dtype=int)
        return X, y

    def train_user_model(self, username: str, *, force: bool = False) -> TrainResult:
        username = (username or "").strip()
        if not username:
            return TrainResult(success=False, username="", reason="missing_username")

        user = db.session.query(User).filter(User.username == username).one_or_none()
        if not user:
            return TrainResult(
                success=False,
                username=username,
                reason="user_not_found",
                message="User not found",
            )

        existing_same_backend = self.get_model_row(username)
        if (not force) and existing_same_backend:
            return TrainResult(
                success=True,
                username=username,
                threshold=float(existing_same_backend.threshold),
                model_id=int(existing_same_backend.id),
                reason="already_trained",
                message="SVM model already exists",
            )

        rows = self._load_training_rows()
        rows = self._filter_complete_user_rows(rows, username)
        X_all, y_all = self._rows_to_xy(rows, username)

        if X_all.shape[0] == 0:
            return TrainResult(
                success=False,
                username=username,
                reason="no_training_rows",
                message="No enrollment rows found for training",
            )

        n_genuine = int(np.sum(y_all == 1))
        n_impostor = int(np.sum(y_all == 0))
        if n_genuine < 2 or n_impostor < 2:
            return TrainResult(
                success=False,
                username=username,
                reason="insufficient_class_balance",
                message=(
                    "Not enough data to train one-vs-rest model. "
                    f"genuine={n_genuine}, impostor={n_impostor}"
                ),
            )

        from sklearn.model_selection import train_test_split
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
        from sklearn.svm import SVC

        try:
            X_train, X_temp, y_train, y_temp = train_test_split(
                X_all,
                y_all,
                test_size=0.4,
                stratify=y_all,
                random_state=42,
            )
            X_val, X_test, y_val, y_test = train_test_split(
                X_temp,
                y_temp,
                test_size=0.5,
                stratify=y_temp,
                random_state=42,
            )
        except Exception as exc:
            return TrainResult(
                success=False,
                username=username,
                reason="split_failed",
                message=str(exc),
            )

        best_model = None
        best_eer = 1.0
        best_threshold = None
        best_params: Dict[str, Any] = {}

        for c_val in self.PARAM_GRID["C"]:
            for gamma in self.PARAM_GRID["gamma"]:
                model = Pipeline(
                    [
                        ("scaler", StandardScaler()),
                        (
                            "svc",
                            SVC(
                                kernel="rbf",
                                C=c_val,
                                gamma=gamma,
                                class_weight="balanced",
                                probability=True,
                                random_state=42,
                            ),
                        ),
                    ]
                )
                model.fit(X_train, y_train)
                val_probs = model.predict_proba(X_val)[:, 1]
                eer, thr = _compute_eer_threshold(y_val, val_probs)
                if eer < best_eer:
                    best_eer = float(eer)
                    best_threshold = float(thr)
                    best_model = model
                    best_params = {
                        "kernel": "rbf",
                        "C": c_val,
                        "gamma": gamma,
                        "class_weight": "balanced",
                        "probability": True,
                        "random_state": 42,
                    }

        if best_model is None or best_threshold is None:
            return TrainResult(
                success=False,
                username=username,
                reason="training_failed",
                message="Unable to select a best SVM model",
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

        # Upsert by username, replacing model regardless of previous backend type.
        row = self.get_model_row_any(username)
        if row is None:
            row = UserMLModel(
                user_id=int(user.id),
                username=username,
                model_blob=blob,
                threshold=float(best_threshold),
                feature_names_json=json.dumps(FEATURE_COLUMNS),
                model_type=self.MODEL_TYPE,
                sklearn_version=None,
                metrics_json=json.dumps(metrics),
                train_params_json=json.dumps(best_params),
                n_samples_total=int(X_all.shape[0]),
                n_genuine=n_genuine,
                n_impostor=n_impostor,
                created_at=_now_utc(),
                updated_at=_now_utc(),
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
            success=True,
            username=username,
            threshold=float(best_threshold),
            eer=float(best_eer),
            metrics=metrics,
            model_id=int(row.id),
            reason="trained",
            message="SVM model trained successfully",
        )

    def verify(self, username: str, features: Dict[str, Any]) -> Dict[str, Any]:
        username = (username or "").strip()
        if not username:
            return {
                "success": False,
                "verified": False,
                "reason": "missing_username",
            }

        row = self.get_model_row(username)
        if row is None:
            return {
                "success": False,
                "verified": False,
                "reason": "model_not_found",
            }

        try:
            model, feature_names = self._get_cached_runtime(row)

            x: List[float] = []
            for name in feature_names:
                val = features.get(name, 0.0)
                if isinstance(val, (list, dict)):
                    val = 0.0
                try:
                    x.append(float(val))
                except Exception:
                    x.append(0.0)

            X = np.asarray([x], dtype=float)
            prob = float(model.predict_proba(X)[0, 1])
            threshold = float(row.threshold)
            verified = bool(prob >= threshold)

            if prob >= 0.90:
                conf = "high"
            elif prob >= 0.70:
                conf = "medium"
            elif prob >= threshold:
                conf = "low"
            else:
                conf = "failed"

            return {
                "success": True,
                "verified": verified,
                "score": round(prob, 4),
                "threshold": round(threshold, 4),
                "confidence": conf,
                "model_id": int(row.id),
                "method": "svm_rbf_probability",
            }
        except Exception as exc:
            return {
                "success": False,
                "verified": False,
                "reason": "predict_failed",
                "error": str(exc),
            }


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
