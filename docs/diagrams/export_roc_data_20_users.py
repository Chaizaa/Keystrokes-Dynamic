"""Export per-user ROC data (FPR/TPR/AUC/EER point) for 20 subjects.

This script rebuilds the one-vs-rest TEST split per user (same random state used
in training), runs each saved user model, and writes ROC-ready JSON for plotting.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import auc, roc_curve
from sklearn.model_selection import train_test_split


DATA_PATH = Path("ml/dataset_railway_20260315.csv")
MODEL_DIR = Path("ml/models_v2")
OUTPUT_PATH = Path("docs/diagrams/roc_data_20_users.json")

DROP_COLUMNS = [
    "subject_code",
    "name_initial",
    "device_info",
    "repetition",
    "H_vector",
    "DD_vector",
    "UD_vector",
    "UU_vector",
    "DU_vector",
    "created_at",
    "event_type",
]


def compute_eer_point(y_true: np.ndarray, probs: np.ndarray) -> tuple[float, float]:
    fpr, tpr, _ = roc_curve(y_true, probs)
    fnr = 1.0 - tpr
    idx = int(np.argmin(np.abs(fpr - fnr)))
    return float(fpr[idx]), float(tpr[idx])


def main() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATA_PATH}")
    if not MODEL_DIR.exists():
        raise FileNotFoundError(f"Model directory not found: {MODEL_DIR}")

    df = pd.read_csv(DATA_PATH)

    subject_counts = df["subject_code"].value_counts()
    valid_users = sorted(subject_counts[subject_counts >= 100].index.tolist())

    df_filtered = df[df["subject_code"].isin(valid_users)].reset_index(drop=True)

    drop_cols_present = [c for c in DROP_COLUMNS if c in df_filtered.columns]
    X_all = df_filtered.drop(columns=drop_cols_present)
    subjects = df_filtered["subject_code"]

    roc_data: dict[str, dict[str, object]] = {}

    for user in valid_users:
        model_path = MODEL_DIR / f"{user}.pkl"
        if not model_path.exists():
            # Skip users without trained models.
            continue

        model = joblib.load(model_path)

        y = (subjects == user).astype(int)

        # Rebuild the exact split pattern from training script.
        _, X_temp, _, y_temp = train_test_split(
            X_all,
            y,
            test_size=0.4,
            stratify=y,
            random_state=42,
        )
        _, X_test, _, y_test = train_test_split(
            X_temp,
            y_temp,
            test_size=0.5,
            stratify=y_temp,
            random_state=42,
        )

        # Align feature order to what each model expects.
        if hasattr(model, "feature_names_in_"):
            cols = list(model.feature_names_in_)
            missing = [c for c in cols if c not in X_test.columns]
            if missing:
                raise ValueError(f"Missing required model features for {user}: {missing}")
            X_test = X_test[cols]

        probs = model.predict_proba(X_test)[:, 1]
        fpr, tpr, _ = roc_curve(y_test, probs)
        roc_auc = float(auc(fpr, tpr))
        eer_x, eer_y = compute_eer_point(y_test.to_numpy(), probs)

        roc_data[user] = {
            "fpr": [float(x) for x in fpr.tolist()],
            "tpr": [float(x) for x in tpr.tolist()],
            "auc": round(roc_auc, 6),
            "eer_point": [round(eer_x, 6), round(eer_y, 6)],
        }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(roc_data, f, indent=2)

    print(f"Saved: {OUTPUT_PATH}")
    print(f"Users exported: {len(roc_data)}")


if __name__ == "__main__":
    main()
