# SVM Workspace (Phase 1)

This folder contains standalone SVM training and evaluation code for keystroke
biometric verification.

Current scope (Phase 1):
- Prepare data from `dataset_entries` + `dataset_subjects`.
- Train per-subject one-vs-rest SVM models.
- Use `probability=True` (Option A) to produce probability scores.
- Compute and store EER-based thresholds.
- Save evaluation outputs in `ml/svm/result`.
- Optionally save trained model artifacts in `ml/svm/models`.

## Folder structure

- `common.py`: shared constants and metric helpers.
- `data_loader.py`: SQLite loaders and subject filters.
- `train_svm.py`: train + evaluate + (optional) persist models.
- `evaluate_svm.py`: evaluate saved SVM models.
- `models/`: model artifacts (`.joblib`) when `--save-models` is enabled.
- `result/`: run summaries and metrics outputs.

## Conservative defaults

- Entry filter: subjects with exactly 100 entries (`--entry-filter exact`).
- Temporal split: train pool uses repetitions `<= 80`, test uses `> 80`.
- Validation split inside train pool: stratified, default `--val-size 0.25`.

## Train command

Run from project root:

```bash
python ml/svm/train_svm.py --db-path data/biometric_auth_railway_20260315_174850.db --save-models
```

Without model persistence (metrics only):

```bash
python ml/svm/train_svm.py --db-path data/biometric_auth_railway_20260315_174850.db
```

## Evaluate command

```bash
python ml/svm/evaluate_svm.py --db-path data/biometric_auth_railway_20260315_174850.db
```
