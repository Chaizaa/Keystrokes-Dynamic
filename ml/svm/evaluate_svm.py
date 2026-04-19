"""Evaluate saved SVM artifacts on dataset test partition."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from common import (
    FEATURE_COLUMNS,
    compute_binary_metrics,
    compute_eer_threshold,
    ensure_dir,
    now_utc_iso,
)
from data_loader import load_joined_dataset, select_subjects_by_entry_count


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate saved SVM model artifacts.")
    parser.add_argument("--db-path", default="data/biometric_auth_railway_20260315_174850.db")
    parser.add_argument("--required-entries", type=int, default=100)
    parser.add_argument("--entry-filter", choices=["exact", "minimum"], default="exact")
    parser.add_argument("--train-repetition-cutoff", type=int, default=80)
    parser.add_argument("--model-dir", default="ml/svm/models")
    parser.add_argument("--result-dir", default="ml/svm/result")
    return parser


def main() -> None:
    args = _build_parser().parse_args()

    model_dir = Path(args.model_dir)
    result_dir = ensure_dir(args.result_dir)

    if not model_dir.exists():
        raise SystemExit(f"Model directory not found: {model_dir}")

    model_files = sorted(model_dir.glob("*_svm.joblib"))
    if not model_files:
        raise SystemExit("No saved model artifacts found. Train first with --save-models.")

    df = load_joined_dataset(args.db_path)
    df = select_subjects_by_entry_count(df, args.required_entries, mode=args.entry_filter)

    import joblib

    rows: List[Dict[str, float]] = []

    for model_file in model_files:
        artifact = joblib.load(model_file)
        subject_code = artifact["subject_code"]
        model = artifact["model"]
        threshold = float(artifact["threshold"])

        # Evaluate only rows in test partition to mirror train script behavior.
        genuine_test = df[(df["subject_code"] == subject_code) & (df["repetition"] > args.train_repetition_cutoff)]
        impostor_test = df[(df["subject_code"] != subject_code) & (df["repetition"] > args.train_repetition_cutoff)]
        test = pd.concat([genuine_test, impostor_test], axis=0, ignore_index=True)

        if test.empty:
            continue

        y_test = (test["subject_code"] == subject_code).astype(int).to_numpy(dtype=int)
        X_test = test[FEATURE_COLUMNS].to_numpy(dtype=float)

        probs = model.predict_proba(X_test)[:, 1]
        auc = float(roc_auc_score(y_test, probs))
        eer, _ = compute_eer_threshold(y_test, probs)
        metrics = compute_binary_metrics(y_test, probs, threshold)

        rows.append(
            {
                "subject_code": subject_code,
                "threshold": threshold,
                "test_auc": auc,
                "test_eer": float(eer),
                "test_accuracy": float(metrics["accuracy"]),
                "test_far": float(metrics["FAR"]),
                "test_frr": float(metrics["FRR"]),
                "n_test": int(len(test)),
                "model_file": model_file.name,
            }
        )

    if not rows:
        raise SystemExit("No evaluable models found for selected data partition.")

    result_df = pd.DataFrame(rows).sort_values("subject_code")
    out_csv = result_dir / "svm_evaluation_metrics.csv"
    result_df.to_csv(out_csv, index=False)

    summary = {
        "evaluated_at": now_utc_iso(),
        "db_path": args.db_path,
        "model_dir": str(model_dir),
        "subjects_evaluated": int(len(result_df)),
        "metrics": {
            "mean_test_auc": float(result_df["test_auc"].mean()),
            "mean_test_eer": float(result_df["test_eer"].mean()),
            "median_test_eer": float(result_df["test_eer"].median()),
            "p90_test_eer": float(result_df["test_eer"].quantile(0.90)),
        },
    }

    out_summary = result_dir / "svm_evaluation_summary.json"
    with out_summary.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("Saved:")
    print(f"- {out_csv}")
    print(f"- {out_summary}")


if __name__ == "__main__":
    main()
