# API Documentation

## Overview

The Keystrokes-Dynamic API is organized into six domain-specific blueprints, each handling a distinct concern in the biometric authentication workflow. This modular structure replaced the monolithic `api.py` during the recent refactoring.

**Base URL**: `/api`

## Architecture

### Blueprint Modules

```
app/blueprints/api/
├── __init__.py           # Blueprint registration & re-exports
├── _shared.py            # Common utilities, response builders
├── enrollment.py         # User enrollment workflow (100 samples)
├── login.py              # User authentication + biometric verification
├── verification.py       # Standalone biometric verification
├── user.py               # User profile management
├── two_factor.py         # 2FA code submission & verification
└── dataset.py            # Research dataset collection
```

### Shared Response Format

All endpoints use consistent response wrapper (from `_shared.to_json()`):

```python
{
  "success": true | false,
  "data": { ... },          # Endpoint-specific data
  "error": "error_code",    # Only if success=false
  "message": "Human-readable message"
}
```

---

## Endpoints by Module

### 1. **Enrollment** (`enrollment.py`)

Manages 100-keystroke sample collection for new users.

#### `POST /api/enroll/start`
Begin enrollment session for a new user.

**Request**:
```json
{
  "username": "john_doe",
  "password": "SecurePass123!",
  "email": "john@example.com"
}
```

**Response** (201 Created):
```json
{
  "success": true,
  "data": {
    "enrollment_id": "uuid-here",
    "status": "started",
    "samples_collected": 0,
    "samples_needed": 100
  }
}
```

#### `GET /api/enroll/status`
Check current enrollment progress.

**Query Parameters**:
- `username` (string, required)

**Response**:
```json
{
  "success": true,
  "data": {
    "samples_collected": 42,
    "samples_needed": 100,
    "enrollment_complete": false,
    "can_attempt_login": false
  }
}
```

#### `POST /api/enroll/submit`
Submit keystroke samples during enrollment.

**Request**:
```json
{
  "subject_code": "john_doe",
  "keystroke_data": [...],  // Raw keydown/keyup events
  "target_phrase": "the quick brown fox"
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "samples_collected": 43,
    "samples_needed": 100,
    "enrollment_complete": false,
    "message": "Sample 43/100 recorded"
  }
}
```

---

### 2. **Login** (`login.py`)

Handles user authentication with password + biometric verification.

#### `POST /api/login`
Authenticate user with password and keystroke biometrics.

**Request**:
```json
{
  "username": "john_doe",
  "password": "SecurePass123!",
  "keystroke_data": [...]  // Raw keydown/keyup events from login form
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "authenticated": true,
    "verified": true,
    "biometric_score": 0.92,
    "confidence": "high",
    "requires_2fa": true,
    "session_token": "token-here"
  }
}
```

**Response** (401 Unauthorized):
```json
{
  "success": false,
  "error": "invalid_credentials",
  "message": "Invalid username or password"
}
```

---

### 3. **Verification** (`verification.py`)

Standalone biometric verification endpoint.

#### `POST /api/verify`
Verify keystroke biometrics for enrolled user.

**Request**:
```json
{
  "username": "john_doe",
  "keystroke_data": [...]
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "verified": true,
    "score": 0.92,
    "threshold": 0.70,
    "confidence": "high",
    "method": "random_forest"
  }
}
```

**Response** when model not ready:
```json
{
  "success": false,
  "error": "training_in_progress",
  "message": "Model training is in progress. Please try again shortly."
}
```

---

### 4. **User** (`user.py`)

User profile and account management.

#### `GET /api/user/profile`
Get authenticated user's profile.

**Headers**:
- `Authorization: Bearer <token>`

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "user_id": 123,
    "username": "john_doe",
    "email": "john@example.com",
    "enrollment_status": "complete",
    "samples_collected": 100,
    "two_fa_enabled": true
  }
}
```

#### `PUT /api/user/password`
Change user password.

**Request**:
```json
{
  "current_password": "OldPass123!",
  "new_password": "NewPass456!"
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Password updated successfully"
}
```

---

### 5. **Two-Factor Auth** (`two_factor.py`)

2FA code handling.

#### `POST /api/2fa/send`
Send 2FA code via email.

**Request**:
```json
{
  "username": "john_doe"
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "message": "2FA code sent to john@example.com"
}
```

#### `POST /api/2fa/verify`
Verify 2FA code.

**Request**:
```json
{
  "username": "john_doe",
  "code": "123456"
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "data": {
    "verified": true,
    "session_token": "new-token-here"
  }
}
```

---

### 6. **Dataset** (`dataset.py`)

Research dataset collection endpoints. Subjects provide their own password (not a fixed phrase) that they type 100 times during collection.

#### `POST /api/dataset/register`
Register a new research subject with their password.

**Request**:
```json
{
  "name_initial": "J",
  "password": "MySecurePass2024!"
}
```

**Response** (201 Created):
```json
{
  "success": true,
  "subject_code": "s001",
  "subject_id": 456,
  "collected": 0,
  "total_samples": 100,
  "session_token": "abc123def..."
}
```

**Notes**:
- Password must be 6-128 characters
- Subject code is auto-generated (s001, s002, etc.)
- Session token is HMAC-protected and must be included in all /submit requests

#### `POST /api/dataset/submit`
Submit keystroke samples for research dataset. Subject types their registered password 100 times.

**Headers**:
- `X-Session-Token: <token>` (from /register response)

**Request**:
```json
{
  "subject_code": "s001",
  "raw_events": [
    {"type": "keydown", "key": "M", "timestamp": 1234567890123},
    {"type": "keyup", "key": "M", "timestamp": 1234567890145},
    ...
  ]
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "collected": 42,
  "total_samples": 100,
  "all_done": false,
  "progress": {"collected": 42, "total": 100}
}
```

**Validation**:
- Backend reconstructs password from keystroke pattern
- Must match the password hash from registration
- If mismatch: returns 400 error "Kata sandi tidak sesuai..."

#### `GET /api/dataset/status/<subject_code>`
Check progress for a subject.

**Path Parameters**:
- `subject_code` (e.g., s001, s001234)

**Response** (200 OK):
```json
{
  "success": true,
  "subject_code": "s001",
  "total_entries": 42,
  "is_complete": false,
  "collected": 42,
  "total_samples": 100,
  "session_token": "abc123def..."
}
```

#### `GET /api/dataset/export`
Download full dataset as CSV or JSON (admin/research only).

**Authentication**:
- Header: `X-Export-Key: <EXPORT_KEY>`
- Or fallback query param: `?key=<EXPORT_KEY>` (deprecated, logged with warning)

**Query Parameters**:
- `format`: "csv" (default) or "json"

**Response** (200 OK - CSV):
```
subject_code,name_initial,device_info,repetition,H_vector,...
s001,J,Chrome/Windows,1,"[0.12, 0.15, ...]",...
s001,J,Chrome/Windows,2,"[0.11, 0.14, ...]",...
```

**Response** (200 OK - JSON):
```json
[
  {
    "subject_code": "s001",
    "name_initial": "J",
    "device_info": "Chrome/Windows",
    "repetition": 1,
    "H_vector": [0.12, 0.15, ...],
    "H_mean": 0.123,
    ...
  },
  ...
]
```

---

## Dataset Collection Workflow

```
1. POST /api/dataset/register
   ↓ (Admin: sets password they'll type 100 times)
   → Returns subject_code (s001), session_token

2. POST /api/dataset/submit (repeat 100 times)
   ↓ (Subject: types their password, sends keystroke data)
   → Backend verifies password hash matches
   → Records features (H_mean, DD_std, etc.)

3. GET /api/dataset/status/<subject_code>
   ↓ (Check progress: collected=42/100)

4. GET /api/dataset/export (admin/research)
   ↓ (Download all data for ML analysis)
   → Available as CSV or JSON
```

**Key Difference from /api/login**:
- Regular login: arbitrary keystroke pattern, password checked separately
- Dataset: password IS the keystroke pattern (reconstructed from timing), must match exactly

---

## Authentication & Security

### Rate Limiting
- **Per-user**: 5 failed attempts per 15 minutes blocks account temporarily
- **Per-endpoint**: 100 requests per minute per IP
- **Development**: Disabled with `DEV_LENIENT_RATELIMIT=1`

### CSRF Protection
All POST/PUT/DELETE requests require CSRF token in:
- Form field: `csrf_token`
- Header: `X-CSRFToken`

### Password Requirements
- **Minimum length**: 8 characters
- **Complexity**: Must include uppercase, lowercase, number, and special character
- **Strength check**: Recommended ≥ 12 characters

---

## Keystroke Data Format

Raw keystroke events sent to the API:

```python
keystroke_data = [
  {
    "type": "keydown",
    "key": "t",
    "timestamp": 1234567890123
  },
  {
    "type": "keyup",
    "key": "t",
    "timestamp": 1234567890145
  },
  # ... more events
]
```

The backend processes these into feature vectors:
- **Hold times**: Key press duration (H_mean, H_std, etc.)
- **Press-press intervals**: Time between key presses (DD_mean, etc.)
- **Release-press intervals**: Time from release to next press (DU_mean, etc.)

---

## Error Codes

| Code | Status | Description |
|---|---|---|
| `invalid_credentials` | 401 | Username/password mismatch |
| `user_not_found` | 404 | User doesn't exist |
| `verification_failed` | 403 | Biometric verification failed |
| `training_in_progress` | 202 | Model training not complete yet |
| `insufficient_enrollment` | 400 | Not enough samples collected |
| `rate_limit_exceeded` | 429 | Too many requests |
| `invalid_2fa_code` | 403 | Incorrect 2FA code |

---

## Adding New Endpoints

### 1. Create Function in Appropriate Blueprint

Example: Adding a new endpoint to `verification.py`

```python
# app/blueprints/api/verification.py

@api_bp.route("/rescore", methods=["POST"])
def rescore_sample():
    """Re-evaluate a keystroke sample with updated model."""
    from flask import request

    data = request.get_json() or {}
    username = data.get("username")

    if not username:
        return to_json(False, error="missing_username")

    # ... implementation ...

    return to_json(True, data={"rescored": True})
```

### 2. Use Response Wrapper

All responses should use `_shared.to_json()`:

```python
from app.blueprints.api._shared import to_json

# Success
return to_json(True, data={"key": "value"})

# Error
return to_json(False, error="error_code", message="Human message"), 400
```

### 3. Add Integration Test

```python
# tests/integration/test_new_endpoint.py

def test_rescore_sample(client):
    """Test rescore endpoint."""
    response = client.post("/api/rescore", json={
        "username": "test_user",
        # ... data ...
    })
    assert response.status_code == 200
    assert response.json["data"]["rescored"] is True
```

### 4. Document in This File

Add endpoint documentation following the template above.

---

## Common Workflows

### User Registration + Login

```
1. POST /api/enroll/start
   ↓ (create user account)
2. POST /api/enroll/submit (repeat 100 times)
   ↓ (collect keystroke samples)
3. [Backend trains RandomForest model]
   ↓
4. POST /api/login (user tries biometric login)
   ↓ (verify with trained model)
5. POST /api/2fa/send (optional 2FA)
   ↓
6. POST /api/2fa/verify
   ↓ (returns session token)
```

### Standalone Biometric Verification

```
1. POST /api/verify (user provides keystroke)
   ↓ (compares to enrollment samples)
2. Returns: verified: true|false, score: 0.0-1.0
```

### Research Dataset Collection

```
1. POST /api/dataset/register
   ↓ (researcher: sets their own password to type 100 times)
   → Returns subject_code (s001), session_token

2. POST /api/dataset/submit (repeat 100 times)
   ↓ (research subject: types their password, raw keystroke events sent)
   → Backend reconstruction verifies password hash matches
   → Extracts and stores features (H_mean, DD_std, etc.)

3. GET /api/dataset/status/<subject_code>
   ↓ (check progress: collected=42/100)

4. GET /api/dataset/export
   ↓ (admin: download dataset as CSV/JSON with EXPORT_KEY)
```

---

## Performance Tips

- **Keystroke capture**: Collect at least 50 events (> 20 characters)
- **Model training**: First model takes 2-5 seconds; subsequent logins < 100ms
- **Batch submissions**: Don't send keystroke samples one-by-one; batch 3-5 samples per request

---

## Support & Debugging

### Check User Enrollment Status
```bash
curl -X GET "http://localhost:5000/api/enroll/status?username=john_doe"
```

### View Model Metrics
- Check database: `SELECT * FROM user_ml_models WHERE username = 'john_doe'`
- Fields: `threshold`, `metrics_json` (contains EER, FPR, FNR)

### Enable Debug Logging
```python
# In config.py
FLASK_ENV = 'development'
LOG_LEVEL = 'DEBUG'
```

---

**Last Updated**: 2026-03-23
**API Version**: 1.0 (Modular Blueprint Architecture)
