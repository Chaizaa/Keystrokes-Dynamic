"""ML model training + persistence service.

Implements the per-user RandomForest approach from `ml/ml_pta.py`:
- one-vs-rest classification: genuine=user, impostor=other users
- train/val/test split: 60/20/20 stratified
- model selection: minimize EER on validation set
- threshold: the EER threshold on validation set

Models and thresholds are stored in the DB table `user_ml_models`.
"""

from __future__ import annotations

import io
import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

from app.models import User, UserMLModel, UsersVector, db


FEATURE_COLUMNS: List[str] = [
    "H_mean",
    "H_std",
    "H_min",
    "H_max",
    "H_cv",
    "DD_mean",
    "DD_std",
    "DD_min",
    "DD_max",
    "DD_cv",
    "UD_mean",
    "UD_std",
    "UD_min",
    "UD_max",
    "UD_cv",
    "UU_mean",
    "UU_std",
    "UU_min",
    "UU_max",
    "UU_cv",
    "DU_mean",
    "DU_std",
    "DU_min",
    "DU_max",
    "DU_cv",
    "total_duration",
    "typing_speed",
]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _compute_metrics(y_true: np.ndarray, probs: np.ndarray, threshold: float) -> Dict[str, float]:
    """Match `compute_metrics` in ml_pta.py."""
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
    """Return (eer, threshold) same as `compute_eer_threshold` in ml_pta.py."""
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


class MLModelService:
    """Train, store, and use per-user RandomForest models."""

    # Mirrors `param_grid` values in ml_pta.py
    PARAM_GRID: Dict[str, List[Any]] = {
        "n_estimators": [200, 400, 600],
        "max_depth": [None, 10, 20, 30],
        # NOTE: ml_pta.py defines min_samples_split but does not loop over it.
        # We keep the same behaviour for reproducibility.
        "min_samples_leaf": [1, 2, 4],
        "max_features": ["sqrt", "log2"],
    }

    def get_model_row(self, username: str) -> Optional[UserMLModel]:
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
        db.session.delete(row)
        db.session.commit()
        return True

    def _serialize_model(self, model) -> bytes:
        import joblib

        buf = io.BytesIO()
        joblib.dump(model, buf)
        return buf.getvalue()

    def _deserialize_model(self, blob: bytes):
        import joblib

        buf = io.BytesIO(blob)
        return joblib.load(buf)

    def _load_training_rows(self) -> List[UsersVector]:
        """Load all enrollment rows used as training pool."""
        return (
            db.session.query(UsersVector)
            .filter(
                (UsersVector.event_type == "enrollment")
                | (UsersVector.data_type == "enrollment")
            )
            .all()
        )

    def _rows_to_xy(self, rows: Iterable[UsersVector], target_username: str) -> Tuple[np.ndarray, np.ndarray]:
        X_list: List[List[float]] = []
        y_list: List[int] = []

        for r in rows:
            # Must have username to label
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
        """Train (or retrain) a user model using the ml_pta procedure."""
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

        if (not force) and self.get_model_row(username):
            row = self.get_model_row(username)
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
                success=False,
                username=username,
                reason="no_training_rows",
                message="No enrollment rows found for training",
            )

        # Need both classes for one-vs-rest
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

        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split

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

        # Grid search (manual loop), mirrors ml_pta.py
        for n in self.PARAM_GRID["n_estimators"]:
            for depth in self.PARAM_GRID["max_depth"]:
                for leaf in self.PARAM_GRID["min_samples_leaf"]:
                    for feat in self.PARAM_GRID["max_features"]:
                        model = RandomForestClassifier(
                            n_estimators=n,
                            max_depth=depth,
                            min_samples_leaf=leaf,
                            max_features=feat,
                            class_weight="balanced",
                            random_state=42,
                            n_jobs=-1,
                        )
                        model.fit(X_train, y_train)
                        val_probs = model.predict_proba(X_val)[:, 1]
                        eer, thr = _compute_eer_threshold(y_val, val_probs)
                        if eer < best_eer:
                            best_eer = float(eer)
                            best_threshold = float(thr)
                            best_model = model
                            best_params = {
                                "n_estimators": n,
                                "max_depth": depth,
                                "min_samples_leaf": leaf,
                                "max_features": feat,
                                "random_state": 42,
                                "class_weight": "balanced",
                            }

        if best_model is None or best_threshold is None:
            return TrainResult(
                success=False,
                username=username,
                reason="training_failed",
                message="Unable to select a best model",
            )

        # Evaluate on test (ml_pta logs both train and test; we store test summary)
        test_probs = best_model.predict_proba(X_test)[:, 1]
        test_metrics = _compute_metrics(y_test, test_probs, best_threshold)
        test_eer, _ = _compute_eer_threshold(y_test, test_probs)

        metrics = {
            "best_eer_val": best_eer,
            "threshold": best_threshold,
            "test": {**test_metrics, "EER": float(test_eer)},
        }

        # Serialize model to bytes
        blob = self._serialize_model(best_model)

        # Persist row (upsert by username)
        row = self.get_model_row(username)
        if row is None:
            row = UserMLModel(
                user_id=int(user.id),
                username=username,
                model_blob=blob,
                threshold=float(best_threshold),
                feature_names_json=json.dumps(FEATURE_COLUMNS),
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
            row.metrics_json = json.dumps(metrics)
            row.train_params_json = json.dumps(best_params)
            row.n_samples_total = int(X_all.shape[0])
            row.n_genuine = n_genuine
            row.n_impostor = n_impostor
            row.updated_at = _now_utc()

        db.session.commit()

        return TrainResult(
            success=True,
            username=username,
            threshold=float(best_threshold),
            eer=float(best_eer),
            metrics=metrics,
            model_id=int(row.id),
            reason="trained",
            message="Model trained successfully",
        )

    def verify(self, username: str, features: Dict[str, Any]) -> Dict[str, Any]:
        """Predict proba and apply per-user threshold."""

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
            model = self._deserialize_model(row.model_blob)
            try:
                feature_names = json.loads(row.feature_names_json)
            except Exception:
                feature_names = FEATURE_COLUMNS

            # Align input
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
                "method": "random_forest",
            }
        except Exception as exc:
            return {
                "success": False,
                "verified": False,
                "reason": "predict_failed",
                "error": str(exc),
            }


ml_model_service = MLModelService()

# --- Background training helpers -----------------------------------------
# Tracks usernames whose model is currently being trained in a daemon thread.
# Prevents duplicate concurrent grid-search runs for the same user.
_training_in_progress: set = set()
_training_lock = threading.Lock()


def schedule_background_training(app, username: str, *, force: bool = False) -> bool:
    """Kick off model training for *username* in a background daemon thread.

    Returns True if a new training thread was started, False if one was already
    running for that user (or if the model already exists and force=False).

    The caller must pass the current Flask ``app`` instance (obtained with
    ``current_app._get_current_object()``) so the thread can push an app
    context around the SQLAlchemy calls.
    """
    username = (username or "").strip()
    if not username:
        return False

    with _training_lock:
        if username in _training_in_progress:
            return False  # already training
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
