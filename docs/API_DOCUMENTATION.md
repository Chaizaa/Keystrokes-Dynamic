# API Documentation
**Keystrokes-Dynamic Biometric Authentication API**  
**Version**: 2.0  
**Date**: December 24, 2024

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

### 2. User Registration

**Endpoint**: `POST /api/register`  
**Description**: Create new user account with password  
**Authentication**: None  
**CSRF**: Exempt

#### Request Body
```json
{
  "username": "string",
  "password": "string"
}
```

**Parameters**:
- `username` (string, required): Unique username (3-50 chars)
- `password` (string, required): Strong password (8-128 chars)

#### Response

**Success (201 Created)**:
```json
{
  "success": true,
  "message": "User registered successfully",
  "user_id": 123,
  "next_step": "enrollment"
}
```

**Validation Error (400 Bad Request)**:
```json
{
  "success": false,
  "error": "Password must be at least 8 characters"
}
```

**Duplicate User (409 Conflict)**:
```json
{
  "success": false,
  "error": "Username already exists"
}
```

#### Examples

**cURL**:
```bash
curl -X POST http://localhost:5000/api/register \
  -H "Content-Type: application/json" \
  -d '{"username": "john_doe", "password": "SecurePass123!"}'
```

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
  "password": "string",
  "H_vector": [0.123, 0.145, 0.167, ...],
  "DD_vector": [0.050, 0.045, 0.052, ...],
  "UD_vector": [0.173, 0.190, 0.219, ...],
  "attempt": 1
}
```

**Parameters**:
- `username` (string, required): Username for enrollment
- `password` (string, required): User's password
- `H_vector` (array, required): Hold time vector (milliseconds)
- `DD_vector` (array, required): Down-Down time vector (milliseconds)
- `UD_vector` (array, required): Up-Down time vector (milliseconds)
- `attempt` (integer, required): Sample number (1-20)

**Vector Format**:
- Each vector contains timing values for each keystroke
- Values should be in seconds (float)
- Vector lengths must match password length

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
  "error": "Invalid vector format",
  "details": "H_vector length mismatch"
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
const keystrokeData = {
  username: 'john_doe',
  password: 'SecurePass123!',
  H_vector: [0.123, 0.145, 0.167, 0.134, 0.156, ...],
  DD_vector: [0.050, 0.045, 0.052, 0.048, 0.051, ...],
  UD_vector: [0.173, 0.190, 0.219, 0.182, 0.207, ...],
  attempt: 1
};

const response = await fetch('/api/register_sample', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify(keystrokeData)
});

const result = await response.json();
console.log(`Progress: ${result.progress_percentage}%`);
console.log(`Quality Score: ${result.quality_score}`);
```

---

### 4. Keystroke Verification (Login)

**Endpoint**: `POST /api/verify`  
**Description**: Verify user identity through keystroke biometric analysis  
**Authentication**: None (creates session on success)  
**CSRF**: Exempt  
**Rate Limit**: 5 attempts per minute per IP

#### Request Body
```json
{
  "username": "string",
  "password": "string",
  "H_vector": [0.123, 0.145, 0.167, ...],
  "DD_vector": [0.050, 0.045, 0.052, ...],
  "UD_vector": [0.173, 0.190, 0.219, ...]
}
```

**Parameters**:
- `username` (string, required): Username to verify
- `password` (string, required): User's password
- `H_vector` (array, required): Hold time vector
- `DD_vector` (array, required): Down-Down time vector
- `UD_vector` (array, required): Up-Down time vector

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
    # Step 2: Verify with keystroke data
    verify_response = requests.post(
        'http://localhost:5000/api/verify',
        json={
            'username': 'john_doe',
            'password': 'SecurePass123!',
            'H_vector': [0.123, 0.145, ...],
            'DD_vector': [0.050, 0.045, ...],
            'UD_vector': [0.173, 0.190, ...]
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

### 6. Password Reset

**Endpoint**: `POST /api/reset_password`  
**Description**: Change user password (requires current password)  
**Authentication**: Required  
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
  "error": "Password must be at least 8 characters"
}
```

---

### 7. Logout

**Endpoint**: `POST /api/logout`  
**Description**: End user session  
**Authentication**: Required  
**CSRF**: Protected

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
| `/api/check_username` | 30 requests | 1 minute | Per IP |
| `/api/register` | 5 requests | 1 hour | Per IP |
| `/api/register_sample` | 10 requests | 1 minute | Per user |
| `/api/verify` | 5 requests | 1 minute | Per IP |
| `/api/reset_password` | 3 requests | 1 hour | Per user |

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

### Keystroke Vector Format

```python
{
  "H_vector": [float],   # Hold times (key press duration)
  "DD_vector": [float],  # Down-Down times (key to key)
  "UD_vector": [float],  # Up-Down times (release to press)
  "length": int,         # Number of keystrokes
  "timestamp": str,      # ISO 8601 timestamp
  "data_type": str       # "enrollment" or "verification"
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
    
    def register(self, username, password):
        """Register new user"""
        response = self.session.post(
            f'{self.base_url}/api/register',
            json={'username': username, 'password': password}
        )
        return response.json()
    
    def submit_sample(self, username, password, vectors, attempt):
        """Submit enrollment sample"""
        data = {
            'username': username,
            'password': password,
            'H_vector': vectors['H'],
            'DD_vector': vectors['DD'],
            'UD_vector': vectors['UD'],
            'attempt': attempt
        }
        response = self.session.post(
            f'{self.base_url}/api/register_sample',
            json=data
        )
        return response.json()
    
    def verify(self, username, password, vectors):
        """Verify user with keystroke biometrics"""
        data = {
            'username': username,
            'password': password,
            'H_vector': vectors['H'],
            'DD_vector': vectors['DD'],
            'UD_vector': vectors['UD']
        }
        response = self.session.post(
            f'{self.base_url}/api/verify',
            json=data
        )
        return response.json()

# Usage
client = KeystrokeAuthClient()
result = client.register('john_doe', 'SecurePass123!')
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
