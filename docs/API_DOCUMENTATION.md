# API Documentation
**Keystrokes-Dynamic Biometric Authentication API**  
**Version**: 2.0  
**Date**: December 24, 2024

> [!IMPORTANT]
> This file is a historical deep-dive and may contain implementation-era examples.
> For current, code-aligned endpoint contracts and payload schema, use `docs/API.md`.

---

## Overview

RESTful API for keystroke dynamics biometric authentication. Supports user registration with behavioral biometric enrollment and continuous authentication through typing pattern analysis.

**Base URL**: `http://localhost:5000/api`  
**Authentication**: Session-based with Flask-Login  
**Content-Type**: `application/json`

---

## Authentication Flow

### Registration & Enrollment
```
1. Check Username → 2. Submit 10-20 Samples → 3. Complete Enrollment → 4. Account Active
```

### Login & Verification
```
1. Check Username → 2. Submit Keystroke Sample → 3. Biometric Verification → 4. Session Created
```

---

## API Endpoints

### 1. Username Availability Check

**Endpoint**: `POST /api/check_username`  
**Description**: Check if username is available and user enrollment status  
**Authentication**: None  
**CSRF**: Exempt

#### Request Body
```json
{
  "username": "string",
  "mode": "register|login"
}
```

**Parameters**:
- `username` (string, required): Username to check (3-50 chars, alphanumeric + underscore)
- `mode` (string, required): Operation mode (`register` or `login`)

#### Response

**Success (200 OK)**:
```json
{
  "available": true,
  "enrollment_status": {
    "enrolled": false,
    "count": 0,
    "ready_for_login": false
  }
}
```

**User Exists (200 OK)**:
```json
{
  "available": false,
  "enrollment_status": {
    "enrolled": true,
    "count": 15,
    "ready_for_login": true
  }
}
```

**Validation Error (400 Bad Request)**:
```json
{
  "error": "Username must be at least 3 characters"
}
```

**Server Error (500 Internal Server Error)**:
```json
{
  "error": "Failed to check username availability"
}
```

#### Examples

**cURL**:
```bash
curl -X POST http://localhost:5000/api/check_username \
  -H "Content-Type: application/json" \
  -d '{"username": "john_doe", "mode": "register"}'
```

**Python**:
```python
import requests

response = requests.post(
    'http://localhost:5000/api/check_username',
    json={'username': 'john_doe', 'mode': 'register'}
)
data = response.json()
print(f"Available: {data['available']}")
```

**JavaScript**:
```javascript
const response = await fetch('/api/check_username', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({username: 'john_doe', mode: 'register'})
});
const data = await response.json();
console.log('Available:', data.available);
```

---

### 2. Account Bootstrap (Current Behavior)

Direct `POST /api/register` is no longer part of the active API surface.

Account bootstrap happens inside `POST /api/register_sample` when the first
enrollment sample is submitted.

Recommended flow:
1. `POST /api/check_username`
2. `POST /api/register_sample`

For the latest request/response contracts, refer to `docs/API.md`.

---

### 3. Keystroke Sample Submission

**Endpoint**: `POST /api/register_sample`  
**Description**: Submit keystroke biometric sample for enrollment  
**Authentication**: None (during enrollment)  
**CSRF**: Exempt  
**Rate Limit**: 10 samples per minute

#### Request Body
```json
{
  "username": "string",
  "email": "string (optional)",
  "events": [
    {"t": 10.0, "evt": "d", "code": "KeyA", "key": "a"},
    {"t": 70.0, "evt": "u", "code": "KeyA", "key": "a"}
  ]
}
```

**Parameters**:
- `username` (string, required): Username for enrollment
- `email` (string, optional): Email used for verification-enabled flow
- `events` (array, required): Keystroke events from frontend

**Event Item Format**:
- `t` (number): Client-side timestamp
- `evt` (string): `d` (keydown) or `u` (keyup)
- `code` (string): Physical key code (`KeyA`, `Backspace`, etc.)
- `key` (string): Display key value

#### Response

**Success (200 OK)**:
```json
{
  "success": true,
  "message": "Sample 5 recorded successfully",
  "samples_count": 5,
  "samples_needed": 10,
  "progress_percentage": 50,
  "quality_score": 0.87,
  "ready_for_login": false
}
```

**Enrollment Complete (200 OK)**:
```json
{
  "success": true,
  "message": "Enrollment complete!",
  "samples_count": 10,
  "samples_needed": 10,
  "progress_percentage": 100,
  "quality_score": 0.92,
  "ready_for_login": true
}
```

**Quality Warning (200 OK)**:
```json
{
  "success": true,
  "message": "Sample recorded with warnings",
  "samples_count": 6,
  "quality_score": 0.65,
  "warnings": [
    "Typing speed inconsistent",
    "High variance detected"
  ]
}
```

**Validation Error (400 Bad Request)**:
```json
{
  "success": false,
  "error": "Invalid event payload"
}
```

**Authentication Error (401 Unauthorized)**:
```json
{
  "success": false,
  "error": "Invalid username or password"
}
```

**Rate Limit (429 Too Many Requests)**:
```json
{
  "success": false,
  "error": "Too many samples submitted. Please wait."
}
```

#### Examples

**JavaScript (Full Sample Submission)**:
```javascript
// Capture keystroke data
const samplePayload = {
  username: 'john_doe',
  email: 'john_doe@example.com',
  events: [
    {t: 10.0, evt: 'd', code: 'KeyS', key: 's'},
    {t: 65.0, evt: 'u', code: 'KeyS', key: 's'},
    {t: 80.0, evt: 'd', code: 'KeyE', key: 'e'},
    {t: 135.0, evt: 'u', code: 'KeyE', key: 'e'}
  ]
};

const response = await fetch('/api/register_sample', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify(samplePayload)
});

const result = await response.json();
console.log(`Progress: ${result.progress_percentage}%`);
console.log(`Quality Score: ${result.quality_score}`);
```

---

### 4. Unified Login

**Endpoint**: `POST /api/login`  
**Description**: Authenticate user identity through keystroke biometric analysis  
**Authentication**: None (creates session on success)  
**CSRF**: Exempt  
**Rate Limit**: 10 attempts per minute per IP

#### Request Body
```json
{
  "username": "string",
  "events": [
    {"t": 10.0, "evt": "d", "code": "KeyA", "key": "a"},
    {"t": 70.0, "evt": "u", "code": "KeyA", "key": "a"}
  ]
}
```

**Parameters**:
- `username` (string, required): Username to verify
- `events` (array, required): Keystroke events in `{t, evt, code, key}` format

#### Response

**Genuine User (200 OK)**:
```json
{
  "success": true,
  "message": "Authentication successful",
  "decision": "genuine",
  "confidence_score": 0.94,
  "confidence_label": "Very High",
  "user_id": 123,
  "session_created": true,
  "metrics": {
    "euclidean_distance": 0.12,
    "cosine_similarity": 0.96,
    "statistical_score": 0.89,
    "primary_metric": "euclidean"
  }
}
```

**Impostor Detected (403 Forbidden)**:
```json
{
  "success": false,
  "message": "Authentication failed - biometric mismatch",
  "decision": "impostor",
  "confidence_score": 0.23,
  "confidence_label": "Low",
  "reason": "Typing pattern does not match enrolled profile",
  "metrics": {
    "euclidean_distance": 0.87,
    "cosine_similarity": 0.34,
    "statistical_score": 0.21
  }
}
```

**Insufficient Enrollment (403 Forbidden)**:
```json
{
  "success": false,
  "message": "Insufficient enrollment data",
  "reason": "User needs to complete enrollment (3/10 samples)",
  "enrollment_progress": 30
}
```

**Invalid Credentials (401 Unauthorized)**:
```json
{
  "success": false,
  "message": "Invalid username or password"
}
```

**Rate Limit (429 Too Many Requests)**:
```json
{
  "success": false,
  "message": "Too many login attempts. Please wait 60 seconds.",
  "retry_after": 60
}
```

#### Verification Metrics

| Metric | Description | Range | Threshold |
|--------|-------------|-------|-----------|
| **Euclidean Distance** | Distance between sample and template | 0.0 - ∞ | < 0.5 (genuine) |
| **Cosine Similarity** | Angular similarity of patterns | 0.0 - 1.0 | > 0.7 (genuine) |
| **Statistical Score** | Statistical feature comparison | 0.0 - 1.0 | > 0.6 (genuine) |
| **Confidence Score** | Overall authentication confidence | 0.0 - 1.0 | > 0.7 (accept) |

**Confidence Labels**:
- **Very High** (0.9 - 1.0): Strong match
- **High** (0.7 - 0.9): Good match
- **Medium** (0.5 - 0.7): Uncertain
- **Low** (0.3 - 0.5): Likely impostor
- **Very Low** (0.0 - 0.3): Impostor detected

#### Examples

**Python (Complete Login Flow)**:
```python
import requests

# Step 1: Check username
check_response = requests.post(
    'http://localhost:5000/api/check_username',
    json={'username': 'john_doe', 'mode': 'login'}
)

if check_response.json()['enrollment_status']['ready_for_login']:
    # Step 2: Login with keystroke events
    verify_response = requests.post(
        'http://localhost:5000/api/login',
        json={
            'username': 'john_doe',
            'events': [
                {'t': 10.0, 'evt': 'd', 'code': 'KeyS', 'key': 's'},
                {'t': 66.0, 'evt': 'u', 'code': 'KeyS', 'key': 's'}
            ]
        }
    )
    
    result = verify_response.json()
    if result['success']:
        print(f"Login successful! Confidence: {result['confidence_score']}")
    else:
        print(f"Login failed: {result['message']}")
```

---

### 5. User Information

**Endpoint**: `GET /api/user/info`  
**Description**: Get current user's enrollment status and statistics  
**Authentication**: Required (Flask-Login session)  
**CSRF**: Protected

#### Response

**Success (200 OK)**:
```json
{
  "username": "john_doe",
  "user_id": 123,
  "enrollment": {
    "enrolled": true,
    "sample_count": 15,
    "ready_for_login": true,
    "enrollment_date": "2024-12-20T10:30:00Z"
  },
  "statistics": {
    "total_logins": 47,
    "successful_verifications": 45,
    "failed_verifications": 2,
    "last_login": "2024-12-24T08:15:00Z",
    "average_confidence": 0.89
  }
}
```

**Unauthenticated (401 Unauthorized)**:
```json
{
  "error": "Authentication required"
}
```

#### Examples

**cURL** (with session cookie):
```bash
curl -X GET http://localhost:5000/api/user/info \
  -H "Cookie: session=your_session_cookie"
```

---

### 6. Authenticated Password Change

**Endpoint**: `POST /api/user/reset_password`  
**Description**: Change current user's password (requires current password)  
**Authentication**: Required (session cookie)  
**CSRF**: Protected

#### Request Body
```json
{
  "current_password": "string",
  "new_password": "string"
}
```

**Parameters**:
- `current_password` (string, required): Current password for verification
- `new_password` (string, required): New password (8-128 chars)

#### Response

**Success (200 OK)**:
```json
{
  "success": true,
  "message": "Password changed successfully",
  "action_required": "Re-enrollment recommended for best security"
}
```

**Invalid Current Password (401 Unauthorized)**:
```json
{
  "success": false,
  "error": "Current password is incorrect"
}
```

**Weak Password (400 Bad Request)**:
```json
{
  "success": false,
  "error": "Password must be at least 1 character"
}
```

---

### 7. Logout (Web Route)

**Endpoint**: `GET /logout`  
**Description**: End user session and redirect to home page  
**Authentication**: Session-aware (safe to call when logged out)  
**CSRF**: N/A (GET route)

#### Response

**Success (200 OK)**:
```json
{
  "success": true,
  "message": "Logged out successfully"
}
```

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Request successful |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Invalid request data |
| 401 | Unauthorized | Authentication required or failed |
| 403 | Forbidden | Access denied (biometric verification failed) |
| 409 | Conflict | Resource already exists (duplicate username) |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server-side error |

### Error Response Format

All errors follow this format:
```json
{
  "success": false,
  "error": "Error message",
  "details": "Optional detailed information",
  "code": "ERROR_CODE"
}
```

### Common Error Codes

| Code | Description |
|------|-------------|
| `INVALID_USERNAME` | Username format invalid |
| `INVALID_PASSWORD` | Password doesn't meet requirements |
| `USERNAME_EXISTS` | Username already taken |
| `USER_NOT_FOUND` | User doesn't exist |
| `INVALID_CREDENTIALS` | Wrong username/password |
| `INSUFFICIENT_ENROLLMENT` | Not enough biometric samples |
| `BIOMETRIC_MISMATCH` | Keystroke pattern doesn't match |
| `RATE_LIMIT_EXCEEDED` | Too many requests |
| `INVALID_VECTOR_FORMAT` | Malformed biometric data |
| `SESSION_EXPIRED` | Authentication session expired |

---

## Rate Limiting

### Limits by Endpoint

| Endpoint | Limit | Window | Scope |
|----------|-------|--------|-------|
| `/api/check_username` | 10 requests | 1 minute | Per IP |
| `/api/register_sample` | 30 requests | 1 minute | Per IP |
| `/api/login` | 10 requests | 1 minute | Per IP |
| `/api/reset_password` | 10 requests | 1 hour | Per IP |
| `/api/user/reset_password` | 3 requests | 1 hour | Authenticated |

### Rate Limit Headers

```http
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 3
X-RateLimit-Reset: 1703419200
```

### Rate Limit Response

```json
{
  "error": "Rate limit exceeded",
  "retry_after": 60,
  "limit": 5,
  "window": "1 minute"
}
```

---

## Security

### Authentication
- **Password Hashing**: Bcrypt (cost factor 12)
- **Session Management**: Flask-Login with secure cookies
- **CSRF Protection**: Enabled for all state-changing operations (except API with exemption)

### Data Protection
- **TLS/SSL**: Required in production (HTTPS only)
- **Secure Headers**: HSTS, X-Frame-Options, CSP
- **Input Validation**: All inputs sanitized and validated
- **SQL Injection**: Protected via SQLAlchemy ORM

### Biometric Data
- **Storage**: Encrypted statistical templates only (no raw keystroke data)
- **Privacy**: Vectors stored as normalized statistical features
- **Revocation**: Re-enrollment required for password change

---

## Data Models

### Keystroke Event Format

```python
{
  "events": [
    {
      "t": float,        # Client-side timestamp
      "evt": str,        # "d" (keydown) or "u" (keyup)
      "code": str,       # Physical key code
      "key": str         # Display key value
    }
  ],
  "event_count": int,
  "event_type": str      # "enrollment" or "verification"
}
```

### Statistical Features

Internally computed from raw vectors:
```python
{
  "mean_H": float,       # Average hold time
  "std_H": float,        # Hold time standard deviation
  "mean_DD": float,      # Average Down-Down time
  "std_DD": float,       # DD standard deviation
  "mean_UD": float,      # Average Up-Down time
  "std_UD": float,       # UD standard deviation
  "skew_H": float,       # Hold time skewness
  "kurtosis_H": float    # Hold time kurtosis
}
```

---

## SDKs & Libraries

### Python Client Example

```python
class KeystrokeAuthClient:
    def __init__(self, base_url="http://localhost:5000"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def check_username(self, username, mode='register'):
        """Check username availability"""
        response = self.session.post(
            f'{self.base_url}/api/check_username',
            json={'username': username, 'mode': mode}
        )
        return response.json()

    def submit_sample(self, username, events, email=None):
        """Submit enrollment sample (and bootstrap account on first sample)."""
        data = {
            'username': username,
            'events': events,
        }
        if email:
            data['email'] = email
        response = self.session.post(
            f'{self.base_url}/api/register_sample',
            json=data
        )
        return response.json()

    def login(self, username, events):
        """Login user with keystroke biometrics."""
        data = {
            'username': username,
            'events': events,
        }
        response = self.session.post(
            f'{self.base_url}/api/login',
            json=data
        )
        return response.json()

# Usage
client = KeystrokeAuthClient()
result = client.submit_sample(
    'john_doe',
    events=[
        {'t': 10.0, 'evt': 'd', 'code': 'KeyS', 'key': 's'},
        {'t': 66.0, 'evt': 'u', 'code': 'KeyS', 'key': 's'},
    ],
    email='john_doe@example.com'
)
```

---

## Changelog

### Version 2.0 (December 2024)
- ✅ Migrated to service layer architecture
- ✅ Added comprehensive error handling
- ✅ Implemented rate limiting
- ✅ Enhanced security headers
- ✅ Standardized JSON responses
- ✅ Added confidence scoring
- ✅ Improved enrollment progress tracking

### Version 1.0 (Initial)
- Basic keystroke authentication
- User registration and login
- SQLite database storage

---

## Support

**Documentation**: [/docs](/docs)  
**GitHub**: [Chaizaa/Keystrokes-Dynamic](https://github.com/Chaizaa/Keystrokes-Dynamic)  
**Issues**: [GitHub Issues](https://github.com/Chaizaa/Keystrokes-Dynamic/issues)

---

**Last Updated**: December 24, 2024  
**API Version**: 2.0  
**Status**: Production Ready ✅
