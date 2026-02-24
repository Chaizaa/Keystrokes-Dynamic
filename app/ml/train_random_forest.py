# app/ml/train_random_forest.py
import json
from pathlib import Path
from typing import Dict, List, Any, Tuple

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score, classification_report
from sklearn.model_selection import train_test_split

from app.ml.feature_builder import build_feature_matrix


def _load_jsonl(path: str) -> List[Dict[str, Any]]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def prepare_binary_labels(rows: List[Dict[str, Any]], target_user: str) -> Tuple[np.ndarray, np.ndarray]:
    """
    y=1 jika sample milik target_user, y=0 jika bukan.
    Cocok untuk model per-user (user-specific verifier).
    """
    X = build_feature_matrix(rows)
    y = np.array([1 if r.get("username") == target_user else 0 for r in rows], dtype=int)
    return X, y


def train_rf_binary(X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    clf = RandomForestClassifier(
        n_estimators=300,
        max_depth=12,
        min_samples_leaf=5,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    clf.fit(X_train, y_train)

    prob = clf.predict_proba(X_test)[:, 1]
    pred = (prob >= 0.5).astype(int)

    metrics = {
        "roc_auc": float(roc_auc_score(y_test, prob)) if len(np.unique(y_test)) > 1 else None,
        "report": classification_report(y_test, pred, output_dict=True),
    }
    return {"model": clf, "metrics": metrics}


def save_model(bundle: Dict[str, Any], out_path: str):
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, out_path)


def main():
    # contoh:
    # python -m app.ml.train_random_forest --data data/train_samples.jsonl --target user1 --out models/rf_user1.joblib
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="Path JSONL samples")
    parser.add_argument("--target", required=True, help="Target username")
    parser.add_argument("--out", required=True, help="Output model file")
    args = parser.parse_args()

    rows = _load_jsonl(args.data)
    X, y = prepare_binary_labels(rows, args.target)

    if X.shape[0] < 30:
        raise ValueError("Data terlalu sedikit. Minimal saran 30+ sample.")
    if len(np.unique(y)) < 2:
        raise ValueError("Label hanya satu kelas. Butuh genuine + impostor.")

    result = train_rf_binary(X, y)
    bundle = {
        "type": "rf_binary_user_model",
        "target_user": args.target,
        "feature_dim": int(X.shape[1]),
        "model": result["model"],
        "metrics": result["metrics"],
        "threshold": 0.7,  # bisa dituning per user
    }
    save_model(bundle, args.out)

    print("Training selesai.")
    print(json.dumps(result["metrics"], indent=2))


if __name__ == "__main__":
    main()
