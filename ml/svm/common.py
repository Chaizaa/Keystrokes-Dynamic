"""Shared utilities for SVM training and evaluation scripts."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Tuple

import numpy as np


FEATURE_COLUMNS = [
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


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dir(path: str | Path) -> Path:
    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    return out


def compute_eer_threshold(y_true: np.ndarray, scores: np.ndarray) -> Tuple[float, float]:
    """Compute EER and threshold from score values."""
    from sklearn.metrics import roc_curve

    fpr, tpr, thresholds = roc_curve(y_true, scores)
    fnr = 1.0 - tpr
    idx = int(np.argmin(np.abs(fpr - fnr)))
    eer = float((fpr[idx] + fnr[idx]) / 2.0)
    threshold = float(thresholds[idx])
    return eer, threshold


def compute_binary_metrics(y_true: np.ndarray, scores: np.ndarray, threshold: float) -> Dict[str, float]:
    """Compute verification metrics at a fixed threshold."""
    from sklearn.metrics import confusion_matrix

    y_pred = (scores >= threshold).astype(int)
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
