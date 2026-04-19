"""Train per-subject SVM models for keystroke verification.

Phase 1 goals:
- standalone training/evaluation pipeline
- probability output (Option A)
- conservative default split
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from common import (
    FEATURE_COLUMNS,
    compute_binary_metrics,
    compute_eer_threshold,
    ensure_dir,
    now_utc_iso,
)
from data_loader import load_joined_dataset, select_subjects_by_entry_count


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train per-subject SVM models.")
    parser.add_argument("--db-path", default="data/biometric_auth_railway_20260315_174850.db")
    parser.add_argument("--required-entries", type=int, default=100)
    parser.add_argument("--entry-filter", choices=["exact", "minimum"], default="exact")
    parser.add_argument("--train-repetition-cutoff", type=int, default=80)
    parser.add_argument("--val-size", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--c", type=float, default=10.0)
    parser.add_argument("--gamma", default="scale")
    parser.add_argument("--model-dir", default="ml/svm/models")
    parser.add_argument("--result-dir", default="ml/svm/result")
    parser.add_argument("--save-models", action="store_true")
    return parser


def _prepare_subject_split(df: pd.DataFrame, subject_code: str, cutoff: int) -> Dict[str, pd.DataFrame]:
    genuine = df[df["subject_code"] == subject_code].sort_values("repetition")
    impostor = df[df["subject_code"] != subject_code].sort_values(["subject_code", "repetition"])

    train_pool = pd.concat(
        [
            genuine[genuine["repetition"] <= cutoff],
            impostor[impostor["repetition"] <= cutoff],
        ],
        axis=0,
        ignore_index=True,
    )

    test_set = pd.concat(
        [
            genuine[genuine["repetition"] > cutoff],
            impostor[impostor["repetition"] > cutoff],
        ],
        axis=0,
        ignore_index=True,
    )

    train_pool["target"] = (train_pool["subject_code"] == subject_code).astype(int)
    test_set["target"] = (test_set["subject_code"] == subject_code).astype(int)
    return {"train_pool": train_pool, "test_set": test_set}


def main() -> None:
    args = _build_parser().parse_args()

    model_dir = ensure_dir(args.model_dir)
    result_dir = ensure_dir(args.result_dir)

    df = load_joined_dataset(args.db_path)
    df = select_subjects_by_entry_count(df, args.required_entries, mode=args.entry_filter)
    subjects: List[str] = sorted(df["subject_code"].unique().tolist())

    if not subjects:
        raise SystemExit("No eligible subjects found for the requested entry filter.")

    per_subject: List[Dict[str, float]] = []

    print(f"Eligible subjects: {len(subjects)}")
    print(f"Total rows: {len(df)}")

    for subject_code in subjects:
        split = _prepare_subject_split(df, subject_code, cutoff=args.train_repetition_cutoff)
        train_pool = split["train_pool"]
        test_set = split["test_set"]

        X_pool = train_pool[FEATURE_COLUMNS].to_numpy(dtype=float)
        y_pool = train_pool["target"].to_numpy(dtype=int)
        X_test = test_set[FEATURE_COLUMNS].to_numpy(dtype=float)
        y_test = test_set["target"].to_numpy(dtype=int)

        X_train, X_val, y_train, y_val = train_test_split(
            X_pool,
            y_pool,
            test_size=args.val_size,
            random_state=args.seed,
            stratify=y_pool,
        )

        model = Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "svc",
                    SVC(
                        kernel="rbf",
                        C=args.c,
                        gamma=args.gamma,
                        class_weight="balanced",
                        probability=True,
                        random_state=args.seed,
                    ),
                ),
            ]
        )

        model.fit(X_train, y_train)
        val_probs = model.predict_proba(X_val)[:, 1]
        val_eer, threshold = compute_eer_threshold(y_val, val_probs)

        # Refit on full train pool after threshold selection.
        model.fit(X_pool, y_pool)

        test_probs = model.predict_proba(X_test)[:, 1]
        test_auc = float(roc_auc_score(y_test, test_probs))
        test_eer, _ = compute_eer_threshold(y_test, test_probs)
        test_metrics = compute_binary_metrics(y_test, test_probs, threshold)

        row = {
            "subject_code": subject_code,
            "threshold": float(threshold),
            "val_eer": float(val_eer),
            "test_auc": float(test_auc),
            "test_eer": float(test_eer),
            "test_accuracy": float(test_metrics["accuracy"]),
            "test_far": float(test_metrics["FAR"]),
            "test_frr": float(test_metrics["FRR"]),
            "n_train_pool": int(len(train_pool)),
            "n_test": int(len(test_set)),
        }
        per_subject.append(row)

        if args.save_models:
            import joblib

            artifact = {
                "subject_code": subject_code,
                "model": model,
                "threshold": float(threshold),
                "feature_names": FEATURE_COLUMNS,
                "backend": "svm_rbf_probability",
                "model_params": {
                    "kernel": "rbf",
                    "C": args.c,
                    "gamma": args.gamma,
                    "class_weight": "balanced",
                    "probability": True,
                    "random_state": args.seed,
                },
                "trained_at": now_utc_iso(),
            }
            out_path = model_dir / f"{subject_code}_svm.joblib"
            joblib.dump(artifact, out_path)

    df_metrics = pd.DataFrame(per_subject).sort_values("subject_code")
    metrics_csv = result_dir / "svm_per_subject_metrics.csv"
    df_metrics.to_csv(metrics_csv, index=False)

    summary = {
        "run_at": now_utc_iso(),
        "db_path": args.db_path,
        "entry_filter": args.entry_filter,
        "required_entries": int(args.required_entries),
        "train_repetition_cutoff": int(args.train_repetition_cutoff),
        "val_size": float(args.val_size),
        "subjects": int(len(subjects)),
        "rows": int(len(df)),
        "save_models": bool(args.save_models),
        "metrics": {
            "mean_test_auc": float(df_metrics["test_auc"].mean()),
            "mean_test_eer": float(df_metrics["test_eer"].mean()),
            "median_test_eer": float(df_metrics["test_eer"].median()),
            "p90_test_eer": float(df_metrics["test_eer"].quantile(0.90)),
        },
    }

    summary_json = result_dir / "svm_run_summary.json"
    with summary_json.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("Saved:")
    print(f"- {metrics_csv}")
    print(f"- {summary_json}")
    if args.save_models:
        print(f"- models in {model_dir}")


if __name__ == "__main__":
    main()
