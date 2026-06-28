"""
Shared abstract base for per-user ML model services (RandomForest & SVM).

Centralises all logic that is identical between the two backends:
  - TrainResult dataclass
  - Shared helper functions (_now_utc, _compute_metrics, _compute_eer_threshold)
  - Model CRUD (get_model_row, get_model_row_any, delete_model)
  - Serialisation via skops (with legacy joblib fallback)
  - Runtime Caching logic (OrderedDict LRU cache)
  - Dataset loading and feature matrix building (_load_training_rows, _rows_to_xy)
  - Background training scaffold (schedule_background_training, is_training_in_progress)
  - Confidence label logic (_confidence_label)
"""
from __future__ import annotations

import io
import json
import threading
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple,Sequence

import numpy as np
from sqlalchemy import or_, select

from app.models import User, UserMLModel, UsersVector, db


# ---------------------------------------------------------------------------
# Feature column order — shared by all backends
# ---------------------------------------------------------------------------
FEATURE_COLUMNS: List[str] = [
    "H_mean", "H_std", "H_min", "H_max", "H_cv",
    "DD_mean", "DD_std", "DD_min", "DD_max", "DD_cv",
    "UD_mean", "UD_std", "UD_min", "UD_max", "UD_cv",
    "UU_mean", "UU_std", "UU_min", "UU_max", "UU_cv",
    "DU_mean", "DU_std", "DU_min", "DU_max", "DU_cv",
    "total_duration",
    "typing_speed",
]


# ---------------------------------------------------------------------------
# Shared data class
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Shared pure helpers
# ---------------------------------------------------------------------------
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _compute_metrics(
    y_true: np.ndarray,
    probs: np.ndarray,
    threshold: float,
) -> Dict[str, float]:
    """Compute confusion-matrix-derived metrics at a fixed threshold."""
    from sklearn.metrics import confusion_matrix

    y_pred = (probs >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    accuracy = (tp + tn) / (tp + tn + fp + fn)
    far = fp / (fp + tn) if (fp + tn) != 0 else 0.0
    frr = fn / (fn + tp) if (fn + tp) != 0 else 0.0
    return {
        "TP": float(tp), "TN": float(tn),
        "FP": float(fp), "FN": float(fn),
        "accuracy": float(accuracy),
        "FAR": float(far),
        "FRR": float(frr),
    }


def _compute_eer_threshold(
    y_true: np.ndarray,
    probs: np.ndarray,
) -> Tuple[float, float]:
    """Return (eer, threshold) at the Equal Error Rate operating point."""
    from sklearn.metrics import roc_curve

    fpr, tpr, thresholds = roc_curve(y_true, probs)
    fnr = 1.0 - tpr
    idx = int(np.argmin(np.abs(fpr - fnr)))
    eer = float((fpr[idx] + fnr[idx]) / 2.0)
    threshold = float(thresholds[idx])
    return eer, threshold


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------
class BaseMLModelService(ABC):
    """Abstract base class for per-user ML model services."""

    MODEL_TYPE: str  # must be set by subclass
    PARAM_GRID: Dict[str, List[Any]]  # must be set by subclass

    # Configuration for runtime caching
    CACHE_MAX_SIZE = 128

    def __init__(self):
        # LRU cache: (username, model_id, updated_marker) -> (deserialized_model, feature_names)
        self._runtime_cache: "OrderedDict[Tuple[str, int, str], Tuple[Any, List[str]]]" = OrderedDict()
        self._runtime_cache_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Model CRUD
    # ------------------------------------------------------------------
    def get_model_row(self, username: str) -> Optional[UserMLModel]:
        if not username:
            return None
        return (
            db.session.execute(
                select(UserMLModel)
                .where(UserMLModel.username == username)
                .where(
                    or_(
                        UserMLModel.model_type == self.MODEL_TYPE,
                        UserMLModel.model_type.is_(None),
                    )
                )
            )
            .scalars()
            .one_or_none()
        )

    def get_model_row_any(self, username: str) -> Optional[UserMLModel]:
        if not username:
            return None
        return (
            db.session.execute(
                select(UserMLModel).where(UserMLModel.username == username)
            )
            .scalars()
            .one_or_none()
        )

    def delete_model(self, username: str) -> bool:
        row = self.get_model_row(username)
        if not row:
            return False
        cached_username = (getattr(row, "username", "") or username or "").strip()
        db.session.delete(row)
        db.session.commit()
        self._invalidate_user_runtime_cache(cached_username)
        return True

    # ------------------------------------------------------------------
    # Runtime caching logic (shared)
    # ------------------------------------------------------------------
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
            stale = [k for k in self._runtime_cache if k[0] == username]
            for k in stale:
                self._runtime_cache.pop(k, None)

    def _get_cached_runtime(self, row: UserMLModel) -> Tuple[Any, List[str]]:
        """Return (model, feature_names) from cache or deserialise if missing."""
        key = self._cache_key_from_row(row)
        with self._runtime_cache_lock:
            cached = self._runtime_cache.get(key)
            if cached is not None:
                self._runtime_cache.move_to_end(key)
                return cached

        # Cache miss: deserialise
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
            while len(self._runtime_cache) > self.CACHE_MAX_SIZE:
                self._runtime_cache.popitem(last=False)
        return payload

    # ------------------------------------------------------------------
    # Serialisation (shared — skops with legacy joblib fallback)
    # ------------------------------------------------------------------
    def _serialize_model(self, model) -> bytes:
        import skops.io as sio

        buf = io.BytesIO()
        sio.dump(model, buf)
        return buf.getvalue()

    @abstractmethod
    def _deserialize_model(self, blob: bytes)-> Any:
        """Load and validate a model from bytes. Backend-specific."""

    # ------------------------------------------------------------------
    # Dataset helpers (shared)
    # ------------------------------------------------------------------
    # def _load_training_rows(self) -> List[UsersVector]:
    #     return (
    #         db.session.execute(
    #             select(UsersVector).where(
    #                 (UsersVector.event_type == "enrollment")
    #                 | (UsersVector.data_type == "enrollment")
    #             )
    #         )
    #         .scalars()
    #         .all()
    #     )
    def _load_training_rows(self) -> Sequence[UsersVector]:
        return (
        db.session.execute(
            select(UsersVector).where(
                (UsersVector.event_type == "enrollment")
                | (UsersVector.data_type == "enrollment")
            )
        )
        .scalars()
        .all()
    )

    def _ensure_class_balance(
        self, X_all: np.ndarray, y_all: np.ndarray, min_impostors: int = 5
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Augment with synthetic impostors when no real impostor users exist.

        Generates samples shifted ±2.5 std from the genuine mean so the binary
        classifier has something to discriminate against.  Only kicks in when
        real impostor count is below min_impostors.
        """
        n_impostor = int(np.sum(y_all == 0))
        if n_impostor >= min_impostors:
            return X_all, y_all

        X_genuine = X_all[y_all == 1]
        if len(X_genuine) < 2:
            return X_all, y_all

        mean = X_genuine.mean(axis=0)
        std = np.clip(X_genuine.std(axis=0), 1e-6, None)
        n_needed = max(min_impostors, len(X_genuine)) - n_impostor

        rng = np.random.RandomState(42)
        centers = [mean + std * 2.5, mean - std * 2.5]
        X_synth = np.array([
            centers[i % 2] + rng.randn(*mean.shape) * std * 0.3
            for i in range(n_needed)
        ], dtype=float)
        y_synth = np.zeros(len(X_synth), dtype=int)

        print(f"[TRAIN] No real impostors — generated {n_needed} synthetic samples for balance")
        return np.vstack([X_all, X_synth]), np.concatenate([y_all, y_synth])

    def _rows_to_xy(
        self,
        rows: Iterable[UsersVector],
        target_username: str,
    ) -> Tuple[np.ndarray, np.ndarray]:
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
            return (
                np.zeros((0, len(FEATURE_COLUMNS)), dtype=float),
                np.zeros((0,), dtype=int),
            )
        return np.asarray(X_list, dtype=float), np.asarray(y_list, dtype=int)

    # ------------------------------------------------------------------
    # Shared verify helper (feature vector building + confidence label)
    # ------------------------------------------------------------------
    def _build_feature_vector(
        self,
        features: Dict[str, Any],
        feature_names: List[str],
    ) -> np.ndarray:
        x: List[float] = []
        for name in feature_names:
            val = features.get(name, 0.0)
            if isinstance(val, (list, dict)):
                val = 0.0
            try:
                x.append(float(val))
            except Exception:
                x.append(0.0)
        return np.asarray([x], dtype=float)

    @staticmethod
    def _confidence_label(prob: float, threshold: float) -> str:
        if prob >= 0.90:
            return "high"
        if prob >= 0.70:
            return "medium"
        if prob >= threshold:
            return "low"
        return "failed"

    # ------------------------------------------------------------------
    # Abstract interface that each backend must implement
    # ------------------------------------------------------------------
    @abstractmethod
    def train_user_model(self, username: str, *, force: bool = False) -> TrainResult:
        """Train or retrain a per-user model and persist it."""

    @abstractmethod
    def verify(self, username: str, features: Dict[str, Any]) -> Dict[str, Any]:
        """Predict and apply threshold; return dict with 'success', 'verified', 'score', …"""