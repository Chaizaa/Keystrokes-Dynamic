# API Function Flow Map

Purpose: quick reference to trace endpoint -> handler -> helpers -> service/model side effects.

## 1) Blueprint Wiring

Source: `app/blueprints/api/__init__.py`

- Exposes shared objects: `api_bp`, `auth_service`, `biometric_service`.
- Re-exports compatibility symbols used by tests (`process_web_events`, `assess_sample_quality`, `db_manager`, `calculate_password_strength`).
- Imports route modules so each `@api_bp.route(...)` decorator is registered.

## 2) Endpoint to Handler Map

| Endpoint | Method | Handler | Module |
|---|---|---|---|
| `/api/check_username` | POST | `check_username` | `app/blueprints/api/enrollment.py` |
| `/api/register_sample` | POST | `register_sample` | `app/blueprints/api/enrollment.py` |
| `/api/pre_verify_password` | POST | `pre_verify_password` | `app/blueprints/api/login.py` |
| `/api/login` | POST | `login` | `app/blueprints/api/login.py` |
| `/api/verify_user` | POST | `verify_user` | `app/blueprints/api/login.py` |
| `/api/2fa/enroll` | POST | `enroll_2fa` | `app/blueprints/api/two_factor.py` |
| `/api/2fa/confirm` | POST | `confirm_2fa` | `app/blueprints/api/two_factor.py` |
| `/api/2fa/verify` | POST | `verify_2fa` | `app/blueprints/api/two_factor.py` |
| `/api/user/info` | GET | `get_user_info` | `app/blueprints/api/user.py` |
| `/api/user/reset_password` | POST | `reset_password` | `app/blueprints/api/user.py` |
| `/api/verify_email` | POST | `verify_email` | `app/blueprints/api/verification.py` |
| `/api/send_verification` | POST | `send_verification` | `app/blueprints/api/verification.py` |
| `/api/send_reset_verification` | POST | `send_reset_verification` | `app/blueprints/api/verification.py` |
| `/api/verify_reset` | POST | `verify_reset` | `app/blueprints/api/verification.py` |
| `/api/reset_password` | POST | `reset_password_public` | `app/blueprints/api/verification.py` |
| `/api/resend_verification` | POST | `resend_verification` | `app/blueprints/api/verification.py` |
| `/api/dataset/export` | GET | `dataset_export` | `app/blueprints/api/dataset.py` |
| `/api/dataset/register` | POST | `dataset_register` | `app/blueprints/api/dataset.py` |
| `/api/dataset/submit` | POST | `dataset_submit` | `app/blueprints/api/dataset.py` |
| `/api/dataset/status/<subject_code>` | GET | `dataset_status` | `app/blueprints/api/dataset.py` |

## 3) Detailed Flow: Username Check

Endpoint: `POST /api/check_username`

Handler: `check_username` in `app/blueprints/api/enrollment.py`

Flow:
1. Parse payload (`username`, optional `mode`).
2. Resolve email-style identifier via `_resolve_username_for_check`.
3. Call `auth_service.check_username_availability(username)`.
4. Call `biometric_service.get_enrollment_status(username)`.
5. If `mode == "login"`, return `_build_check_username_login_response(...)`.
6. Otherwise, return `_build_check_username_register_response(...)`.

Key response fields:
- `status`, `available`, `exists`, `message`
- `can_login`, `enrollment_complete`, `enrollment_count`
- `is_retry`

## 4) Detailed Flow: Register Sample

Endpoint: `POST /api/register_sample`

Handler: `register_sample` in `app/blueprints/api/enrollment.py`

Flow:
1. Parse request with `_extract_register_payload`.
2. Validate minimal payload/username format with `_validate_register_payload`.
3. Get current enrollment status/count via `biometric_service.get_enrollment_status`.
4. Build feature payload with `_prepare_enrollment_features`:
   - `_process_web_events(...)` (via `app.blueprints.api.process_web_events`)
   - `_assess_sample_quality(...)` (via `app.blueprints.api.assess_sample_quality`)
5. Process password/account state with `_handle_password_and_user_flow`:
   - `calculate_password_strength`
   - existing-user password checks
   - `_set_password_on_existing_user` or `_create_user_for_first_sample`
   - `_log_registration_audit`
   - `_send_registration_verification_email`
6. Persist vector record with `_save_enrollment_vector` to `EnrollmentVector` (SQLAlchemy).
7. Recompute enrollment status and progress.
8. Optionally trigger background training with `_schedule_auto_training_if_ready`.
9. Return success payload (`status`, `progress`, `quality`, `password`, `ml_training`).

Important side effects:
- DB write: `EnrollmentVector` row.
- Optional DB updates: `User.password_hash`, `User.email_verification_sent_at`.
- Optional async task: RF/SVM model training when enrollment reaches target.

## 5) Detailed Flow: Login

Endpoints:
- `POST /api/pre_verify_password`
- `POST /api/login`
- `POST /api/verify_user`

Main orchestrator helper chain in `app/blueprints/api/login.py`:
1. `_resolve_login_context`
2. `_check_login_rate_limit`
3. `_extract_login_features`
4. `_validate_login_password`
5. `_run_biometric_login_verification`
6. `_save_verification_vector`
7. `_log_login_attempt`
8. `_log_biometric_login_telemetry`

Outcome summary:
- Password mismatch returns explicit reason (`PASSWORD_MISMATCH`).
- Biometric verification returns score/threshold-driven decision.
- Successful verification updates session + login attempt history.

## 6) Reading Order for New Contributors

Recommended first pass:
1. `app/blueprints/api/__init__.py` (wiring + exports)
2. `app/blueprints/api/enrollment.py` (registration lifecycle)
3. `app/blueprints/api/login.py` (authentication lifecycle)
4. `app/services/auth_service.py` and `app/services/biometric_service.py` (business logic)
5. `app/models/*.py` (persistence schema)

This order gives the fastest understanding from HTTP boundary to storage and model behavior.
