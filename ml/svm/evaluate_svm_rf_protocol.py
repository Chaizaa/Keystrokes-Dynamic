"""Evaluate SVM with the same protocol used by the RandomForest paper run.

Protocol (apple-to-apple with RF draft numbers):
- Subjects filtered by entry count.
- One-vs-rest per subject.
- Stratified split 60/20/20 (train/val/test) with fixed random seed.
- Model selection by minimum validation EER.
- Test metrics computed using the selected validation threshold.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

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
    parser = argparse.ArgumentParser(
        description="Evaluate SVM under RF paper protocol (stratified 60/20/20)."
    )
    parser.add_argument("--db-path", default="data/biometric_auth_railway_20260315_174850.db")
    parser.add_argument("--required-entries", type=int, default=100)
    parser.add_argument("--entry-filter", choices=["exact", "minimum"], default="exact")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--c-grid", nargs="+", type=float, default=[1.0, 10.0, 50.0])
    parser.add_argument("--gamma-grid", nargs="+", default=["scale", "auto"])
    parser.add_argument("--result-dir", default="ml/svm/result")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    result_dir = ensure_dir(args.result_dir)

    df = load_joined_dataset(args.db_path)
    df = select_subjects_by_entry_count(df, args.required_entries, mode=args.entry_filter)
    subjects: List[str] = sorted(df["subject_code"].unique().tolist())
    if not subjects:
        raise SystemExit("No eligible subjects found for the requested entry filter.")

    X_all = df[FEATURE_COLUMNS]
    subject_series = df["subject_code"]

    rows: List[Dict[str, float]] = []

    for subject_code in subjects:
        y = (subject_series == subject_code).astype(int)

        X_train, X_temp, y_train, y_temp = train_test_split(
            X_all,
            y,
            test_size=0.4,
            stratify=y,
            random_state=args.seed,
        )
        X_val, X_test, y_val, y_test = train_test_split(
            X_temp,
            y_temp,
            test_size=0.5,
            stratify=y_temp,
            random_state=args.seed,
        )

        best_model = None
        best_eer = 1.0
        best_threshold = None
        best_params = None

        for c_val in args.c_grid:
            for gamma in args.gamma_grid:
                model = Pipeline(
                    [
                        ("scaler", StandardScaler()),
                        (
                            "svc",
                            SVC(
                                kernel="rbf",
                                C=float(c_val),
                                gamma=gamma,
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

                if val_eer < best_eer:
                    best_eer = float(val_eer)
                    best_threshold = float(threshold)
                    best_model = model
                    best_params = {
                        "C": float(c_val),
                        "gamma": gamma,
                        "class_weight": "balanced",
                        "probability": True,
                        "random_state": int(args.seed),
                    }

        if best_model is None or best_threshold is None or best_params is None:
            continue

        test_probs = best_model.predict_proba(X_test)[:, 1]
        test_auc = float(roc_auc_score(y_test, test_probs))
        test_eer, _ = compute_eer_threshold(y_test, test_probs)
        test_metrics = compute_binary_metrics(y_test, test_probs, best_threshold)

        rows.append(
            {
                "subject_code": subject_code,
                "threshold": float(best_threshold),
                "val_eer": float(best_eer),
                "test_auc": float(test_auc),
                "test_eer": float(test_eer),
                "test_accuracy": float(test_metrics["accuracy"]),
                "test_far": float(test_metrics["FAR"]),
                "test_frr": float(test_metrics["FRR"]),
                "TP": float(test_metrics["TP"]),
                "TN": float(test_metrics["TN"]),
                "FP": float(test_metrics["FP"]),
                "FN": float(test_metrics["FN"]),
                "best_params": json.dumps(best_params),
                "n_train": int(len(X_train)),
                "n_val": int(len(X_val)),
                "n_test": int(len(X_test)),
            }
        )

    if not rows:
        raise SystemExit("No result rows produced. Check data filters.")

    result_df = pd.DataFrame(rows).sort_values("subject_code")
    out_csv = result_dir / "svm_rf_protocol_metrics.csv"
    result_df.to_csv(out_csv, index=False)

    # RF reference values taken from docs/RESEARCH_PAPER_DRAFT.md test summary.
    rf_ref = {
        "accuracy": 0.97813,
        "far": 0.02026,
        "frr": 0.05250,
        "eer": 0.02961,
    }
    svm_avg = {
        "accuracy": float(result_df["test_accuracy"].mean()),
        "far": float(result_df["test_far"].mean()),
        "frr": float(result_df["test_frr"].mean()),
        "eer": float(result_df["test_eer"].mean()),
        "auc": float(result_df["test_auc"].mean()),
    }

    summary = {
        "run_at": now_utc_iso(),
        "protocol": "stratified_60_20_20_one_vs_rest_eer_threshold",
        "db_path": args.db_path,
        "subjects": int(len(result_df)),
        "rows": int(len(df)),
        "svm_average_test": svm_avg,
        "rf_reference_test": rf_ref,
        "delta_svm_minus_rf": {
            "accuracy": float(svm_avg["accuracy"] - rf_ref["accuracy"]),
            "far": float(svm_avg["far"] - rf_ref["far"]),
            "frr": float(svm_avg["frr"] - rf_ref["frr"]),
            "eer": float(svm_avg["eer"] - rf_ref["eer"]),
        },
    }

    out_json = result_dir / "svm_rf_protocol_summary.json"
    with out_json.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("Saved:")
    print(f"- {out_csv}")
    print(f"- {out_json}")
    print("SVM avg test metrics:")
    print(json.dumps(svm_avg, indent=2))


if __name__ == "__main__":
    main()
