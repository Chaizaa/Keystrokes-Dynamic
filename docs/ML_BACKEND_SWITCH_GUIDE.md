# ML Backend Switch Guide

This project supports one active biometric backend at runtime:
- `rf` (RandomForest, default)
- `svm` (SVM RBF with probability output)

The active backend is selected with `ML_BACKEND`.

## 1. Set Backend

In `.env`:

```env
ML_BACKEND=rf
```

Allowed values:
- `rf`
- `svm`

If the value is invalid or missing, the app falls back to `rf`.

## 2. Apply Change

Restart the application process after changing `ML_BACKEND`.

Examples:

```bash
# local development
flask run

# railway (example)
# restart deployment after updating environment variables
```

## 3. Runtime Behavior

- Biometric verification dispatches to the configured backend at request time.
- If a user model does not exist for the selected backend, the app starts background training and asks the user to retry.
- The `user_ml_models` row is updated for the active backend model type during training.

## 4. Recommended Rollout

1. Keep production on `rf` first.
2. Validate `svm` in staging with real enrollment/login flow.
3. Switch production to `svm` during low-traffic window.
4. Monitor login failures and training-in-progress responses.
5. Roll back to `rf` immediately if verification quality degrades.

## 5. Quick Checks

- Confirm app config resolves to expected backend.
- Validate login flow:
  - successful verification path
  - model-missing path (training started/in progress)
- Run unit tests:

```bash
pytest tests/unit/test_ml_backend_mode_switch.py -q
```
