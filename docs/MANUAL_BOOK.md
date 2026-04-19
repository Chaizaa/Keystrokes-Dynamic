# Keystrokes-Dynamic Manual Book

Version: 1.0
Last updated: 2026-04-11
Scope: Developer, maintainer, operator, and deployment manual for this repository.

---

## Table of Contents

1. Purpose and Scope
2. System Overview
3. Architecture
4. Project Structure
5. Local Setup and First Run
6. Configuration Reference
7. Database and Migration Guide
8. Authentication and User Flows
9. API Endpoint Catalog
10. ML Backend Manual (RF and SVM)
11. Dataset Collection Module
12. Scripts and Operational Utilities
13. Deployment Runbook
14. Testing Runbook
15. Security Checklist
16. Troubleshooting Guide
17. Maintenance Playbook
18. Appendix: File Index

---

## 1) Purpose and Scope

This manual book is the operational source of truth for this project as it currently exists in code.

It is written to help you:
- Run the app locally and in production.
- Understand architecture and critical files.
- Operate registration, verification, reset, and dataset flows.
- Manage ML backend mode switching between Random Forest and SVM.
- Deploy safely and debug common failures.

Important: Some legacy docs in the repository describe older flows. This manual is compiled from the active code paths.

---

## 2) System Overview

Keystrokes-Dynamic is a Flask application for keystroke-dynamics-based authentication.

Core behavior:
- User registration captures typing samples.
- User login verifies password and typing behavior.
- The system supports per-user ML model verification.
- ML backend is switchable at runtime:
  - rf (Random Forest)
  - svm (SVC RBF with probability output)
- Includes dataset collection endpoints and public dataset page.
- Includes admin pages, health endpoints, and email verification/reset flows.

Default local database:
- data/biometric_auth.db

Primary runtime entry:
- run.py

Production WSGI command:
- gunicorn run:app --workers 2 --bind 0.0.0.0:$PORT --timeout 120

---

## 3) Architecture

### 3.1 Application Factory

App factory:
- app/__init__.py

What it initializes:
- Flask app
- SQLAlchemy + Migrate
- Flask-Login
- CSRF protection
- Flask-Limiter (supports REDIS_URL)
- Flask-Caching
- Flask-SocketIO
- CORS for /api/* using ALLOWED_ORIGIN
- Optional Flask-Talisman security headers in production

Special runtime guards:
- DATASET_ONLY=1 can restrict public exposure to dataset and static/health paths.
- ML backend value is normalized at startup to rf or svm.

### 3.2 Blueprints

Registered blueprints:
- main: site pages
- auth: login/register/reset/verify pages
- api: JSON API endpoints
- admin: admin dashboard and operations
- dataset: public dataset collection page
- health: migration/health checks

### 3.3 Service Layer

Main services:
- app/services/auth_service.py
- app/services/biometric_service.py
- app/services/ml_model_service.py
- app/services/svm_model_service.py
- app/services/email_service.py

BiometricService is the runtime dispatcher:
- Reads ML_BACKEND from app config/env.
- Routes train and verify calls to RF or SVM backend.

### 3.4 Data Model Layer

Primary model files:
- app/models/user.py
- app/models/keystroke_vector.py
- app/models/user_ml_model.py
- app/models/login_attempt.py
- app/models/dataset.py
- app/models/admin_audit.py
- app/models/client.py

Critical tables:
- users
- users_vectors (keystroke vectors for enrollment/login data)
- user_ml_models (serialized per-user model + threshold)
- login_attempts
- dataset_subjects
- dataset_entries
- admin_audits
- clients

---

## 4) Project Structure

Top-level operational map:

- run.py: app entrypoint
- config.py: config classes and environment settings
- Procfile: production process command
- railway.toml: Railway deploy start command
- app/: core Flask application
- templates/: HTML templates
- static/: JS/CSS/assets
- migrations/: Alembic migration environment
- scripts/: operational and diagnostics scripts
- ml/svm/: standalone SVM training/evaluation workspace
- docs/: project documentation
- data/: local DB and datasets
- tests/: unit and integration tests

Scripts organization:
- scripts/db/: DB helpers
- scripts/diagnostics/: diagnostics scripts
- scripts/: general scripts

---

## 5) Local Setup and First Run

### 5.1 Prerequisites

- Python 3.12+ recommended
- Git
- PowerShell (Windows) or shell (Linux/macOS)

### 5.2 Setup

Windows PowerShell example:

```powershell
cd C:\Users\Hafidz\Desktop\Keystrokes-Dynamic
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

Create env file:

```powershell
Copy-Item .env.example .env
```

### 5.3 Run app (development)

```powershell
python run.py
```

Default local URL:
- http://127.0.0.1:5000

### 5.4 Alternative using Flask CLI

```powershell
$env:FLASK_APP="run:app"
flask run
```

---

## 6) Configuration Reference

Config source:
- config.py
- .env (runtime)
- .env.example (template)

### 6.1 Core

- FLASK_ENV: development | production | testing
- SECRET_KEY: required in production

### 6.2 Database

- DATABASE_TYPE: sqlite or postgres
- DATABASE_PATH: default data/biometric_auth.db
- DATABASE_URL: used when DATABASE_TYPE is not sqlite

### 6.3 Session and security

- SESSION_COOKIE_SECURE
- SESSION_COOKIE_HTTPONLY
- SESSION_COOKIE_SAMESITE
- PERMANENT_SESSION_LIFETIME

### 6.4 Biometric and ML

- MIN_ENROLLMENT_SAMPLES (default 100)
- VERIFICATION_THRESHOLD (default 0.7)
- MAX_LOGIN_ATTEMPTS (default 5)
- ML_BACKEND: rf or svm
  - invalid value automatically falls back to rf

### 6.5 Rate limiting

- RATELIMIT_ENABLED
- RATELIMIT_DEFAULT
- RATELIMIT_STORAGE_URL
- REDIS_URL (Limiter storage_uri fallback)
- DEV_LENIENT_RATELIMIT

### 6.6 Email

- MAIL_SERVER
- MAIL_PORT
- MAIL_USE_TLS
- MAIL_USE_SSL
- MAIL_USERNAME
- MAIL_PASSWORD
- MAIL_DEFAULT_SENDER
- EMAIL_VERIFICATION_EXPIRY_HOURS

### 6.7 Deployment/CORS

- ALLOWED_ORIGIN (CORS for /api/*)
- DATASET_ONLY (1 to lock app to dataset mode)
- EXPORT_KEY (required for dataset export endpoint)

---

## 7) Database and Migration Guide

### 7.1 Local DB path

By default, SQLite DB is stored at:
- data/biometric_auth.db

### 7.2 Alembic migration command

Use in deployment/runtime where schema must be up to date:

```powershell
flask db upgrade
```

Railway start command currently runs migration before gunicorn:
- railway.toml startCommand includes flask db upgrade

### 7.3 Migration health check

Endpoint:
- GET /health/migrations

Purpose:
- Verifies required user columns exist.
- Returns 200 if schema is healthy.
- Returns 503 with missing columns list if out of date.

---

## 8) Authentication and User Flows

### 8.1 Registration and enrollment

Primary endpoints:
- POST /api/check_username
- POST /api/register_sample

Flow summary:
1. Check username availability and enrollment status.
2. Submit typed events to register_sample.
3. Backend processes keystrokes, calculates quality, stores vector.
4. On first sample, creates user if needed and can send verification email.
5. At completion target (recommended samples), background model training can auto-start.

### 8.2 Login flow

Primary endpoint:
- POST /api/login

Behavior:
1. Validates request and rate-limit state.
2. Extracts keystroke features from events.
3. Validates password from reconstructed typed password.
4. Runs biometric verification via active ML backend.
5. If verified:
   - Enforces 2FA if enabled
   - Requires email verification for non-admin accounts
   - Creates Flask login session

### 8.3 Pre-verification

Endpoint:
- POST /api/pre_verify_password

Use:
- Pre-check password + biometrics before final login completion.

### 8.4 Verify user endpoint

Endpoint:
- POST /api/verify_user

Use:
- Direct verification call, also stores verification sample via ORM helper.

### 8.5 Email verification and password reset

Endpoints:
- POST /api/send_verification
- POST /api/verify_email
- POST /api/resend_verification
- POST /api/send_reset_verification
- POST /api/verify_reset
- POST /api/reset_password

Notes:
- Reset flow validates signed token and typed events.
- Reset endpoint stores new enrollment sample and updates password.

### 8.6 2FA flow (TOTP)

Endpoints:
- POST /api/2fa/enroll
- POST /api/2fa/confirm
- POST /api/2fa/verify

---

## 9) API Endpoint Catalog

Base prefix:
- /api

### 9.1 Enrollment

- POST /api/check_username
  - Inputs commonly include username and mode.
  - Returns existence, resumable state, and enrollment counts.

- POST /api/register_sample
  - Inputs: username, events, optional email.
  - Stores enrollment vector and quality result.
  - Can trigger auto background training when target count reached.

### 9.2 Login/verification

- POST /api/pre_verify_password
  - Inputs: username, events

- POST /api/login
  - Inputs: username (or identifier), events
  - Rate-limited and audit-aware.

- POST /api/verify_user
  - Inputs: username, events

### 9.3 User management

- GET /api/user/info (auth required)
- POST /api/user/reset_password (auth required)

### 9.4 Email and reset

- POST /api/verify_email
- POST /api/send_verification
- POST /api/send_reset_verification
- POST /api/verify_reset
- POST /api/reset_password
- POST /api/resend_verification

### 9.5 Two-factor

- POST /api/2fa/enroll
- POST /api/2fa/confirm
- POST /api/2fa/verify

### 9.6 Dataset

- GET /api/dataset/export
- POST /api/dataset/register
- POST /api/dataset/submit
- GET /api/dataset/status/<subject_code>

---

## 10) ML Backend Manual (RF and SVM)

### 10.1 Backend mode switch

Runtime switch:
- ML_BACKEND=rf
- ML_BACKEND=svm

Normalization behavior:
- Any invalid value is coerced to rf.

Dispatcher:
- app/services/biometric_service.py

### 10.2 RF backend (ml_model_service)

Model type metadata:
- RandomForestClassifier

Training pipeline:
- one-vs-rest classification
- stratified split 60/20/20
- grid search over:
  - n_estimators: 200, 400, 600
  - max_depth: None, 10, 20, 30
  - min_samples_leaf: 1, 2, 4
  - max_features: sqrt, log2
- selects model with minimum validation EER
- persists model blob + threshold in user_ml_models

Verification output method string:
- random_forest

### 10.3 SVM backend (svm_model_service)

Model type metadata:
- SVC_RBF_probability

Training pipeline:
- one-vs-rest SVC with probability=True
- stratified split 60/20/20
- grid search:
  - C: 1.0, 10.0, 50.0
  - gamma: scale, auto
- conservative impostor filter:
  - MIN_REQUIRED_ENROLLMENT_ROWS = 100
- threshold chosen from validation EER

Verification output method string:
- svm_rbf_probability

### 10.4 Model persistence

Table:
- user_ml_models

Stored per user:
- model_blob
- threshold
- model_type
- feature_names_json
- metrics_json
- train_params_json
- sample counters

### 10.5 Training triggers

Common triggers:
- Auto training after enrollment completion.
- Lazy background training when verify is called and no model exists.

Returned reasons from verification when no model yet:
- training_started
- training_in_progress

---

## 11) Dataset Collection Module

Public page route:
- GET /dataset

Dataset API workflow:
1. Register respondent: POST /api/dataset/register
2. Receive subject_code and session_token
3. Submit repeated samples: POST /api/dataset/submit
4. Check progress: GET /api/dataset/status/<subject_code>
5. Export dataset: GET /api/dataset/export (requires export key)

Security controls in dataset module:
- Session token is HMAC over subject_code and SECRET_KEY.
- submit requires X-Session-Token header.
- export requires X-Export-Key (preferred) or query fallback.

Dataset constants:
- DATASET_TOTAL_SAMPLES = 100

Stored vectors/statistics in dataset_entries:
- H, DD, UD, UU, DU vectors
- mean/std/min/max/cv for each vector
- total_duration and typing_speed

---

## 12) Scripts and Operational Utilities

Script folder reference:
- scripts/README.md

Common utilities:
- scripts/db/check_db_structure.py
- scripts/db/migrate_db.py
- scripts/diagnostics/test_rounding.py

SVM workspace:
- ml/svm/train_svm.py
- ml/svm/evaluate_svm.py
- ml/svm/evaluate_svm_rf_protocol.py
- ml/svm/result/
- ml/svm/models/

Example commands:

```powershell
python scripts/db/check_db_structure.py
python scripts/diagnostics/test_rounding.py
python ml/svm/train_svm.py --db-path data/biometric_auth_railway_20260315_174850.db
python ml/svm/evaluate_svm_rf_protocol.py --db-path data/biometric_auth_railway_20260315_174850.db
```

---

## 13) Deployment Runbook

### 13.1 Process model

Procfile web command:
- gunicorn run:app --workers 2 --bind 0.0.0.0:$PORT --timeout 120

Railway command:
- flask db upgrade && gunicorn run:app --workers 2 --bind 0.0.0.0:$PORT --timeout 120

### 13.2 Minimum production env checklist

Set these at minimum:
- FLASK_ENV=production
- SECRET_KEY=<strong random value>
- DATABASE_TYPE and DATABASE_URL if using postgres
- SESSION_COOKIE_SECURE=True
- ALLOWED_ORIGIN=<your frontend origin>
- ML_BACKEND=rf (or svm after validation)
- EXPORT_KEY=<for dataset export>
- MAIL_* variables if email flows enabled

### 13.3 First deploy checklist

1. Ensure dependencies installed from requirements.txt
2. Set env variables
3. Run flask db upgrade
4. Verify GET /health/migrations returns status ok
5. Test:
   - registration sample save
   - login flow
   - email verification path
   - dataset endpoints if enabled

---

## 14) Testing Runbook

### 14.1 Run all tests

```powershell
pytest
```

### 14.2 Run focused tests

```powershell
pytest tests/unit/test_ml_backend_mode_switch.py -q
pytest tests/integration -q
```

### 14.3 What to validate after ML/backend changes

- ML_BACKEND invalid value falls back to rf
- Dispatch to SVM when ML_BACKEND=svm
- Dispatch to RF when ML_BACKEND=rf
- Missing model triggers background training reason

---

## 15) Security Checklist

- Use strong SECRET_KEY in production.
- Keep SESSION_COOKIE_SECURE=True in production.
- Restrict ALLOWED_ORIGIN to trusted frontend origins.
- Keep CSRF protection enabled for non-exempt routes.
- Use REDIS_URL-backed limiter in multi-worker deployments.
- Require EXPORT_KEY for dataset export and use header form.
- Avoid logging sensitive token/password values.
- Keep MAIL credentials in environment only.

---

## 16) Troubleshooting Guide

### 16.1 Login fails with model/training reason

Symptom:
- API returns training_started or training_in_progress.

Action:
- Wait for background training to finish.
- Ensure sufficient enrollment samples exist.
- Check active backend and model availability in user_ml_models.

### 16.2 Schema mismatch errors

Symptom:
- User creation or endpoint errors mentioning missing columns/migration.

Action:
- Run flask db upgrade.
- Verify /health/migrations output.

### 16.3 Rate limit issues during local testing

Symptom:
- Frequent 429 or lockout behavior.

Action:
- Set DEV_LENIENT_RATELIMIT=True for local dev.
- Verify RATELIMIT_ENABLED and storage settings.

### 16.4 Email verification not sending

Action:
- Validate MAIL_SERVER, MAIL_PORT, MAIL_USE_TLS/SSL, credentials.
- Check sender format in MAIL_DEFAULT_SENDER.

### 16.5 Dataset submit unauthorized

Symptom:
- 401 invalid session token.

Action:
- Use session_token from register/status.
- Send it in X-Session-Token header.

---

## 17) Maintenance Playbook

### Daily

- Check app startup and basic health endpoint.
- Check login failure trend and suspicious attempts.

### Weekly

- Review rate-limit and auth logs.
- Validate verification quality and user complaints.
- Verify backups for DB and critical docs.

### Monthly

- Review dependency updates and CVE advisories.
- Re-test ML backend behavior in staging.
- Re-validate env vars and secrets rotation policy.

---

## 18) Appendix: File Index

Core runtime:
- run.py
- app/__init__.py
- config.py

Blueprints:
- app/blueprints/main.py
- app/blueprints/auth.py
- app/blueprints/admin.py
- app/blueprints/dataset.py
- app/blueprints/health.py
- app/blueprints/api/__init__.py
- app/blueprints/api/_shared.py
- app/blueprints/api/enrollment.py
- app/blueprints/api/login.py
- app/blueprints/api/verification.py
- app/blueprints/api/user.py
- app/blueprints/api/two_factor.py
- app/blueprints/api/dataset.py

Services:
- app/services/auth_service.py
- app/services/biometric_service.py
- app/services/ml_model_service.py
- app/services/svm_model_service.py
- app/services/email_service.py

Models:
- app/models/user.py
- app/models/keystroke_vector.py
- app/models/user_ml_model.py
- app/models/login_attempt.py
- app/models/dataset.py
- app/models/admin_audit.py
- app/models/client.py

Ops and deployment:
- Procfile
- railway.toml
- requirements.txt
- scripts/README.md
- docs/DEPLOYMENT_GUIDE.md

---

End of manual book.
