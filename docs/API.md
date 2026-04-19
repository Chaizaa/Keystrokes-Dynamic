# API Reference (Current)

This document reflects the currently registered routes under the Flask `api_bp` blueprint.

- Base path: `/api`
- Source of truth: `app/blueprints/api/*.py`
- Frontend event schema: `static/js/keystroke.js`

## Event Payload Schema

Most biometric endpoints accept an `events` array (or `raw_events` for dataset endpoints).

Each event item uses this structure:

```json
{
  "t": 1234.56,
  "evt": "d",
  "code": "KeyA",
  "key": "a"
}
```

Notes:
- `evt`: `d` = keydown, `u` = keyup.
- `t`: client-side timestamp (typically `performance.now()`).
- `code`: physical key code (example: `KeyA`, `Backspace`).
- `key`: rendered character/value.

## Authentication Model

- Browser login uses `POST /api/login` with keystroke events.
- Session-based protected APIs use Flask-Login cookie auth.
- `GET /api/user/info` and `POST /api/user/reset_password` require an authenticated session.

## Enrollment and Login Endpoints

### POST /api/check_username
Checks username/email existence and enrollment state.

Request:

```json
{
  "username": "alice",
  "mode": "login"
}
```

Key responses:
- `200`: user state returned (`exists`, `can_login`, `enrollment_count`).
- `400`: invalid input.

Rate limit: `10 per minute`.

### POST /api/register_sample
Saves one enrollment sample. If this is the first sample, user creation/password initialization can happen in this endpoint.

Request:

```json
{
  "username": "alice",
  "email": "alice@example.com",
  "events": [
    {"t": 10.0, "evt": "d", "code": "KeyA", "key": "a"},
    {"t": 70.0, "evt": "u", "code": "KeyA", "key": "a"}
  ]
}
```

Success response includes:
- `status: "success"`
- `progress.current`
- `progress.target` (currently `100`)
- `progress.complete`
- `quality` and `password_strength`
- optional `ml_training`

Rate limit: `30 per minute`.

### POST /api/pre_verify_password
Performs pre-check before full login flow: password + biometric quick validation.

Request:

```json
{
  "username": "alice",
  "events": [
    {"t": 10.0, "evt": "d", "code": "KeyA", "key": "a"}
  ]
}
```

Typical responses:
- `200`: `{ "valid": true, ... }`
- `403`: password mismatch or rhythm mismatch.
- `404`: user/enrollment not found.

### POST /api/login
Primary login endpoint. Validates password, runs biometric verification, handles lockout/rate-limit logic, and returns 2FA requirement when enabled.

Request:

```json
{
  "username": "alice",
  "events": [
    {"t": 10.0, "evt": "d", "code": "KeyA", "key": "a"}
  ]
}
```

Common response patterns:
- `200`: login success (`success: true`), or `requires_2fa: true`.
- `400`: invalid input, model unavailable, incomplete enrollment.
- `403`: password mismatch / impostor detected / email not verified.
- `404`: user not found or no enrollment.
- `429`: too many failed attempts.

Rate limit: `10 per minute`.

### POST /api/verify_user
Standalone verification endpoint used by some internal/testing flows.

Request:

```json
{
  "username": "alice",
  "events": [
    {"t": 10.0, "evt": "d", "code": "KeyA", "key": "a"}
  ]
}
```

Returns:
- `status: "success"` with verification details, or
- `status: "fail"` / `status: "error"`.

## Email Verification and Password Reset Endpoints

### POST /api/send_verification
Sends a 6-digit email verification code. May create provisional user row when needed.

Request:

```json
{
  "username": "alice",
  "email": "alice@example.com"
}
```

### POST /api/verify_email
Verifies email token/code.

Request:

```json
{
  "username": "alice",
  "token": "123456"
}
```

### POST /api/resend_verification
Resends verification code for an existing user.

Request:

```json
{
  "username": "alice"
}
```

Rate limit: `3 per 15 minutes`.

### POST /api/send_reset_verification
Sends password-reset verification code to account email.

Request:

```json
{
  "username": "alice"
}
```

### POST /api/verify_reset
Verifies reset code and returns signed reset token.

Request:

```json
{
  "username": "alice",
  "token": "123456"
}
```

### POST /api/reset_password
Public reset flow endpoint before login. Saves a new enrollment sample tied to reset.

Request:

```json
{
  "username": "alice",
  "reset_token": "signed-token",
  "events": [
    {"t": 10.0, "evt": "d", "code": "KeyA", "key": "a"}
  ]
}
```

Rate limit: `10 per hour`.

## User Account Endpoints (Session Required)

### GET /api/user/info
Returns current user profile + enrollment status.

Response example:

```json
{
  "username": "alice",
  "email": "alice@example.com",
  "enrollment_count": 100,
  "enrollment_ready": true,
  "verified_logins": 12
}
```

### POST /api/user/reset_password
Resets password for logged-in user and clears enrollment vectors so re-enrollment is required.

Request:

```json
{
  "current_password": "OldPass123!",
  "new_password": "NewPass123!"
}
```

Rate limit: `3 per hour`.

## Two-Factor Authentication Endpoints

### POST /api/2fa/enroll
Generates TOTP secret for user.

Request:

```json
{
  "username": "alice"
}
```

### POST /api/2fa/confirm
Confirms token and enables 2FA.

Request:

```json
{
  "username": "alice",
  "token": "123456"
}
```

### POST /api/2fa/verify
Verifies TOTP token during sign-in flow.

Request:

```json
{
  "username": "alice",
  "token": "123456"
}
```

## Dataset Collection Endpoints

Dataset endpoints support public research data capture and are separate from user login enrollment.

### POST /api/dataset/register
Registers a subject and returns `subject_code` + `session_token`.

Request:

```json
{
  "name_initial": "AH",
  "password": "research-pass"
}
```

Success response includes:
- `subject_code`
- `total_samples`
- `session_token`

Rate limit: `10 per hour`.

### POST /api/dataset/submit
Submits one dataset sample.

Required header:

```http
X-Session-Token: <token from register/status>
```

Request:

```json
{
  "subject_code": "s001",
  "raw_events": [
    {"t": 10.0, "evt": "d", "code": "KeyA", "key": "a"}
  ]
}
```

Rate limit: `200 per hour` (global and subject-aware keying).

### GET /api/dataset/status/<subject_code>
Returns collection progress and refreshed `session_token`.

Rate limit: `60 per minute`.

### GET /api/dataset/export
Exports dataset as CSV or JSON.

Authentication:
- Preferred: `X-Export-Key` header.
- Deprecated fallback: `?key=...` query parameter.

Query:
- `format=csv` (default) or `format=json`.

Rate limit: `10 per minute`.

## Common Error/Reason Values

The API uses endpoint-specific payloads, but common values include:

- `PASSWORD_MISMATCH`
- `impostor_detected`
- `insufficient_enrollment`
- `no_enrollment`
- `rate_limit_exceeded`
- `email_not_verified`
- `invalid_token`
- `expired_token`

## cURL Smoke Tests

### Check username (login mode)

```bash
curl -X POST http://localhost:5000/api/check_username \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","mode":"login"}'
```

### Login (with events)

```bash
curl -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","events":[{"t":10,"evt":"d","code":"KeyA","key":"a"},{"t":70,"evt":"u","code":"KeyA","key":"a"}]}'
```

### Dataset register

```bash
curl -X POST http://localhost:5000/api/dataset/register \
  -H "Content-Type: application/json" \
  -d '{"name_initial":"AH","password":"research-pass"}'
```
