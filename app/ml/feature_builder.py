# app/ml/feature_builder.py
import json
from typing import Dict, List, Any
import numpy as np
from scipy.stats import kurtosis, skew


VECTOR_KEYS = ["H_vector", "DD_vector", "UD_vector", "UU_vector", "DU_vector"]


def _parse_vec(value: Any) -> np.ndarray:
    if value is None:
        return np.array([], dtype=float)
    if isinstance(value, list):
        return np.array(value, dtype=float)
    if isinstance(value, str):
        try:
            return np.array(json.loads(value), dtype=float)
        except Exception:
            return np.array([], dtype=float)
    return np.array([], dtype=float)


def _stats(vec: np.ndarray) -> List[float]:
    # 7 statistik per vector: mean, std, min, max, median, skew, kurtosis
    if vec.size == 0:
        return [0.0] * 7
    return [
        float(np.mean(vec)),
        float(np.std(vec)),
        float(np.min(vec)),
        float(np.max(vec)),
        float(np.median(vec)),
        float(skew(vec)) if vec.size > 2 else 0.0,
        float(kurtosis(vec)) if vec.size > 3 else 0.0,
    ]


def build_feature_vector(sample: Dict[str, Any]) -> List[float]:
    features: List[float] = []
    for k in VECTOR_KEYS:
        vec = _parse_vec(sample.get(k))
        features.extend(_stats(vec))
    return features


def build_feature_matrix(samples: List[Dict[str, Any]]) -> np.ndarray:
    rows = [build_feature_vector(s) for s in samples]
    if not rows:
        return np.zeros((0, len(VECTOR_KEYS) * 7), dtype=float)
    return np.array(rows, dtype=float)
