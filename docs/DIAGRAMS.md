# 🔄 Unified Login System - Flow Diagrams

## 1. Login Flow: Before vs After

### ❌ BEFORE (Dual-Mode - Confusing!)
```
┌─────────────────────────────────────────────────────────┐
│                    USER OPENS /login                     │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│          🤔 USER MUST CHOOSE MODE:                       │
│   ┌─────────────────┐       ┌──────────────────┐        │
│   │Collection Mode  │   OR  │Verification Mode │        │
│   │(Save 10 samples)│       │(Check biometric) │        │
│   └─────────────────┘       └──────────────────┘        │
└────────────────────┬────────────────┬───────────────────┘
                     │                │
         ┌───────────┘                └──────────┐
         │                                       │
         ▼                                       ▼
┌─────────────────┐                    ┌─────────────────┐
│ Collection Mode │                    │Verification Mode│
│                 │                    │                 │
│ 1. User login   │                    │ 1. User login   │
│ 2. Save data    │                    │ 2. Verify       │
│ 3. No verify ❌ │                    │ 3. Accept/Reject│
│ 4. Impostor     │                    │ 4. NO SAVE ❌   │
│    data saved! ❌│                    │                 │
└─────────────────┘                    └─────────────────┘
         │                                       │
         ▼                                       ▼
┌─────────────────────────────────────────────────────────┐
│          DATABASE: user_vectors (MIXED DATA)             │
│  ├─ Enrollment samples                                   │
│  ├─ Verified logins                                      │
│  ├─ Unverified logins                                    │
│  └─ Impostor data with keystroke! ⚠️                     │
└─────────────────────────────────────────────────────────┘
```

### ✅ AFTER (Unified - Simple!)
```
┌─────────────────────────────────────────────────────────┐
│                    USER OPENS /login                     │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│               💚 SINGLE LOGIN FORM                       │
│          [Username] [Password] [Login]                   │
│          (No mode selection needed!)                     │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              UNIFIED LOGIN ENDPOINT                      │
│              /api/login (NEW)                            │
│                                                          │
│  1. Extract keystroke features                           │
│  2. Rate limiting check (5/15 min)                       │
│  3. Get enrollment data (20 samples)                     │
│  4. Pre-verify password hash (fast reject)               │
│  5. Comprehensive verification (9 methods)               │
│  6. ✅ DECISION LOGIC:                                   │
│     ├─ Genuine? → Save to verified_logins               │
│     └─ Impostor? → Log to failed_logins (no keystroke)  │
└────────────────────┬────────────────────────────────────┘
                     │
         ┌───────────┴──────────┐
         │                      │
         ▼                      ▼
┌─────────────────┐    ┌─────────────────┐
│  ✅ GENUINE      │    │  ❌ IMPOSTOR     │
│                 │    │                 │
│ Save to:        │    │ Log to:         │
│ verified_logins │    │ failed_logins   │
│                 │    │                 │
│ ✅ WITH keystroke│    │ ❌ NO keystroke  │
│ ✅ Full details  │    │ ✅ Reason only   │
│ ✅ Score info    │    │ ✅ IP/UA info    │
│                 │    │                 │
│ Redirect /home  │    │ Show error      │
└─────────────────┘    └─────────────────┘
         │                      │
         ▼                      ▼
┌─────────────────────────────────────────────────────────┐
│          DATABASE: CLEAN SEPARATION                      │
│                                                          │
│  ┌─────────────────────────────────────────────┐        │
│  │ enrollment_vectors (Pure training data)     │        │
│  │ - 20 samples per user                       │        │
│  │ - From registration only                    │        │
│  └─────────────────────────────────────────────┘        │
│                                                          │
│  ┌─────────────────────────────────────────────┐        │
│  │ verified_logins (Genuine authentications)   │        │
│  │ - WITH keystroke data                       │        │
│  │ - Verification scores + methods             │        │
│  │ - IP/User Agent logs                        │        │
│  └─────────────────────────────────────────────┘        │
│                                                          │
│  ┌─────────────────────────────────────────────┐        │
│  │ failed_logins (Security log)                │        │
│  │ - NO keystroke data 🔒                      │        │
│  │ - Reason + score only                       │        │
│  │ - IP/User Agent logs                        │        │
│  └─────────────────────────────────────────────┘        │
│                                                          │
│  ┌─────────────────────────────────────────────┐        │
│  │ login_statistics (Daily aggregates)         │        │
│  │ - Total/success/failed counts               │        │
│  │ - Average scores                            │        │
│  │ - Unique users                              │        │
│  └─────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Verification Logic

```
┌─────────────────────────────────────────────────────────┐
│              UNIFIED LOGIN VERIFICATION                  │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│ Step 1: Rate Limiting Check                              │
│ ┌─────────────────────────────────────────────┐          │
│ │ Get recent failed attempts (15 min window)  │          │
│ │ IF failed >= 5 → Return 429 (Rate Limited) │          │
│ └─────────────────────────────────────────────┘          │
└────────────────────┬────────────────────────────────────┘
                     │ OK
                     ▼
┌─────────────────────────────────────────────────────────┐
│ Step 2: Extract Features                                 │
│ ┌─────────────────────────────────────────────┐          │
│ │ Process keystroke events                    │          │
│ │ Calculate: H, DD, UD, UU, DU vectors        │          │
│ │ Hash password                               │          │
│ └─────────────────────────────────────────────┘          │
└────────────────────┬────────────────────────────────────┘
                     │ Features ready
                     ▼
┌─────────────────────────────────────────────────────────┐
│ Step 3: Check Enrollment                                 │
│ ┌─────────────────────────────────────────────┐          │
│ │ Get enrollment samples from DB              │          │
│ │ IF count < 20 → Return 404 (Not enrolled)  │          │
│ └─────────────────────────────────────────────┘          │
└────────────────────┬────────────────────────────────────┘
                     │ Enrollment OK
                     ▼
┌─────────────────────────────────────────────────────────┐
│ Step 4: Pre-Verify Password Hash (Fast Reject)          │
│ ┌─────────────────────────────────────────────┐          │
│ │ Compare: stored_hash vs input_hash          │          │
│ │ IF not match → Return 403 (Wrong password) │          │
│ └─────────────────────────────────────────────┘          │
└────────────────────┬────────────────────────────────────┘
                     │ Hash match
                     ▼
┌─────────────────────────────────────────────────────────┐
│ Step 5: Comprehensive Keystroke Verification            │
│ ┌─────────────────────────────────────────────┐          │
│ │ Run 9 verification methods:                 │          │
│ │ 1. Euclidean Distance                       │          │
│ │ 2. Manhattan Distance                       │          │
│ │ 3. Mahalanobis Distance                     │          │
│ │ 4. IQR Method                               │          │
│ │ 5. Z-Score                                  │          │
│ │ 6. Isolation Forest                         │          │
│ │ 7. Robust Statistics                        │          │
│ │ 8. Consensus Voting                         │          │
│ │ 9. Recommended Method                       │          │
│ │                                             │          │
│ │ → Final decision: Genuine or Impostor?     │          │
│ └─────────────────────────────────────────────┘          │
└────────────────────┬────────────────────────────────────┘
                     │
         ┌───────────┴──────────┐
         │                      │
         ▼                      ▼
┌─────────────────┐    ┌─────────────────┐
│  ✅ GENUINE      │    │  ❌ IMPOSTOR     │
│                 │    │                 │
│ 1. Save to:     │    │ 1. Log to:      │
│    verified_    │    │    failed_      │
│    logins       │    │    logins       │
│                 │    │                 │
│ 2. Return 200   │    │ 2. Return 403   │
│    Success      │    │    Error        │
│                 │    │                 │
│ 3. Redirect     │    │ 3. Show hint    │
│    to /home     │    │    message      │
└─────────────────┘    └─────────────────┘
```

---

## 3. Database Schema Visual

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATABASE ARCHITECTURE                         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ TABLE: enrollment_vectors                                        │
│ Purpose: Pure training data from registration                    │
├─────────────────────────────────────────────────────────────────┤
│ id (PK)                                                          │
│ username                     ← INDEXED                           │
│ password_hash                                                    │
│ timestamp                                                        │
│ H_vector  (Hold times)                                           │
│ DD_vector (Down-Down)                                            │
│ UD_vector (Up-Down)                                              │
│ UU_vector (Up-Up)                                                │
│ DU_vector (Down-Up)                                              │
│ data_type = 'enrollment'                                         │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │ 20 samples per user
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ TABLE: verified_logins                                           │
│ Purpose: Successful authentications (genuine users)              │
├─────────────────────────────────────────────────────────────────┤
│ id (PK)                                                          │
│ username                     ← INDEXED                           │
│ password_hash                                                    │
│ timestamp                    ← INDEXED                           │
│ H_vector                     ✅ WITH keystroke data              │
│ DD_vector                                                        │
│ UD_vector                                                        │
│ UU_vector                                                        │
│ DU_vector                                                        │
│ verification_score           (0.0 - 1.0)                         │
│ recommended_method           (euclidean, manhattan, etc.)        │
│ consensus_accept             (e.g., 8 out of 9)                  │
│ consensus_total                                                  │
│ all_methods_results          (JSON)                              │
│ ip_address                                                       │
│ user_agent                                                       │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ TABLE: failed_logins                                             │
│ Purpose: Security log for failed attempts                        │
├─────────────────────────────────────────────────────────────────┤
│ id (PK)                                                          │
│ username                     ← INDEXED                           │
│ timestamp                    ← INDEXED                           │
│ reason                       (impostor_detected, wrong_password, │
│                               rate_limit_exceeded, etc.)         │
│ ip_address                                                       │
│ user_agent                                                       │
│ verification_score           (optional, if verified)             │
│                              ❌ NO keystroke vectors             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ TABLE: login_statistics                                          │
│ Purpose: Daily aggregated metrics                                │
├─────────────────────────────────────────────────────────────────┤
│ id (PK)                                                          │
│ date                         ← INDEXED (UNIQUE)                  │
│ total_attempts               (verified + failed)                 │
│ successful_logins                                                │
│ failed_logins                                                    │
│ avg_verification_score                                           │
│ unique_users                                                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Security Features Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    SECURITY LAYER DIAGRAM                        │
└─────────────────────────────────────────────────────────────────┘

USER LOGIN ATTEMPT
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 1: Rate Limiting                                           │
│ ┌─────────────────────────────────────────────────────────┐     │
│ │ Check: failed_logins WHERE timestamp > NOW() - 15min   │     │
│ │ IF count >= 5 → BLOCK (429 Rate Limited)              │     │
│ │ Purpose: Prevent brute force attacks                   │     │
│ └─────────────────────────────────────────────────────────┘     │
└────────────────────────┬────────────────────────────────────────┘
                         │ PASS
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 2: Password Hash Verification (Fast Reject)               │
│ ┌─────────────────────────────────────────────────────────┐     │
│ │ Extract: input_hash from keystroke events              │     │
│ │ Compare: stored_hash vs input_hash                     │     │
│ │ IF not match → REJECT (403 Wrong Password)            │     │
│ │ Purpose: Fast reject without expensive keystroke check │     │
│ └─────────────────────────────────────────────────────────┘     │
└────────────────────────┬────────────────────────────────────────┘
                         │ PASS
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 3: Keystroke Biometric Verification (Deep Check)          │
│ ┌─────────────────────────────────────────────────────────┐     │
│ │ Run 9 verification methods:                            │     │
│ │   • Euclidean Distance                                 │     │
│ │   • Manhattan Distance                                 │     │
│ │   • Mahalanobis Distance                               │     │
│ │   • IQR Method                                         │     │
│ │   • Z-Score                                            │     │
│ │   • Isolation Forest                                   │     │
│ │   • Robust Statistics                                  │     │
│ │   • Consensus Voting (8/9 threshold)                   │     │
│ │   • Recommended Method                                 │     │
│ │                                                        │     │
│ │ Final Decision: Genuine or Impostor?                   │     │
│ └─────────────────────────────────────────────────────────┘     │
└────────────────────────┬────────────────────────────────────────┘
                         │
             ┌───────────┴──────────┐
             │                      │
             ▼                      ▼
    ┌─────────────────┐    ┌─────────────────┐
    │  ✅ GENUINE      │    │  ❌ IMPOSTOR     │
    │                 │    │                 │
    │ ACTIONS:        │    │ ACTIONS:        │
    │ 1. Save full    │    │ 1. Log WITHOUT  │
    │    data to      │    │    keystroke    │
    │    verified_    │    │    data to      │
    │    logins       │    │    failed_      │
    │                 │    │    logins       │
    │ 2. Record:      │    │                 │
    │    - Keystroke  │    │ 2. Record only: │
    │    - Score      │    │    - Username   │
    │    - Method     │    │    - Reason     │
    │    - IP/UA      │    │    - Score      │
    │                 │    │    - IP/UA      │
    │ 3. Allow login  │    │                 │
    │ 4. Redirect     │    │ 3. Block login  │
    │    /home        │    │ 4. Show error   │
    └─────────────────┘    └─────────────────┘
```

---

## 5. Data Retention & Cleanup Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                DATA LIFECYCLE MANAGEMENT                         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ ENROLLMENT DATA (Permanent)                                      │
│ ┌─────────────────────────────────────────────────────────┐     │
│ │ enrollment_vectors                                      │     │
│ │ - Created during registration                           │     │
│ │ - 20 samples per user                                   │     │
│ │ - NEVER deleted automatically                           │     │
│ │ - Only deleted when user account deleted                │     │
│ └─────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ VERIFIED LOGINS (30-day retention)                               │
│ ┌─────────────────────────────────────────────────────────┐     │
│ │ verified_logins                                         │     │
│ │ - Created on successful login                           │     │
│ │ - Kept for 30 days                                      │     │
│ │ - Auto-deleted after 30 days                            │     │
│ │ - Aggregated to login_statistics before deletion        │     │
│ └─────────────────────────────────────────────────────────┘     │
│                                                                  │
│ Cleanup Schedule:                                                │
│ ├─ Daily at 3:00 AM (recommended)                                │
│ └─ Command: cleanup_old_verified_logins(days=30)                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ FAILED LOGINS (7-day retention)                                  │
│ ┌─────────────────────────────────────────────────────────┐     │
│ │ failed_logins                                           │     │
│ │ - Created on failed login                               │     │
│ │ - Kept for 7 days (security log)                        │     │
│ │ - Auto-deleted after 7 days                             │     │
│ │ - Used for rate limiting (15-min window)                │     │
│ └─────────────────────────────────────────────────────────┘     │
│                                                                  │
│ Cleanup Schedule:                                                │
│ ├─ Daily at 3:00 AM (recommended)                                │
│ └─ Command: cleanup_old_failed_logins(days=7)                    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ AGGREGATED STATISTICS (Permanent)                                │
│ ┌─────────────────────────────────────────────────────────┐     │
│ │ login_statistics                                        │     │
│ │ - Daily summary of all login activity                   │     │
│ │ - Total/success/failed counts                           │     │
│ │ - Average verification scores                           │     │
│ │ - Unique users count                                    │     │
│ │ - Kept FOREVER (compact data)                           │     │
│ └─────────────────────────────────────────────────────────┘     │
│                                                                  │
│ Aggregation Schedule:                                            │
│ ├─ Daily at 3:00 AM (recommended)                                │
│ └─ Command: aggregate_login_statistics()                         │
└─────────────────────────────────────────────────────────────────┘

AUTOMATED CLEANUP WORKFLOW:
┌─────────────────────────────────────────────────────────────────┐
│ Daily at 3:00 AM (Cron/Task Scheduler)                          │
│                                                                  │
│ python cleanup_maintenance.py --all                              │
│   │                                                              │
│   ├─ 1. Aggregate today's statistics                             │
│   │   └─ Create entry in login_statistics                       │
│   │                                                              │
│   ├─ 2. Delete old verified logins (>30 days)                    │
│   │   └─ DELETE FROM verified_logins WHERE timestamp < NOW-30d  │
│   │                                                              │
│   └─ 3. Delete old failed logins (>7 days)                       │
│       └─ DELETE FROM failed_logins WHERE timestamp < NOW-7d     │
│                                                                  │
│ Result: Database stays lean, statistics preserved forever        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Implementation Timeline

```
┌─────────────────────────────────────────────────────────────────┐
│              IMPLEMENTATION PROGRESS                             │
└─────────────────────────────────────────────────────────────────┘

[✅] Step 1: Database Architecture Design
     │
     ├─ Design 4-table schema
     ├─ Plan migration strategy
     └─ Define indexes for performance
     
[✅] Step 2: Database Migration Script
     │
     ├─ Create migrate_unified_login.py (273 lines)
     ├─ Implement backup_database()
     ├─ Implement create_new_tables()
     ├─ Implement migrate_existing_data()
     ├─ Implement create_indexes()
     └─ Implement verify_migration()
     
[✅] Step 3: Database Functions (db.py)
     │
     ├─ get_enrollment_samples_from_new_table()
     ├─ save_verified_login()
     ├─ log_failed_login()
     ├─ get_verified_login_count()
     ├─ get_failed_login_count_recent()
     ├─ cleanup_old_verified_logins()
     ├─ cleanup_old_failed_logins()
     └─ aggregate_login_statistics()
     
[✅] Step 4: Unified Login Endpoint (app.py)
     │
     ├─ Create /api/login endpoint
     ├─ Implement rate limiting logic
     ├─ Implement two-tier verification
     ├─ Implement conditional save logic
     └─ Implement error handling
     
[✅] Step 5: Simplified Login UI
     │
     ├─ Create login_unified.html (495 lines)
     ├─ Remove mode selection
     ├─ Add username validation
     ├─ Add typing timer
     └─ Add modern styling
     
[✅] Step 6: Testing & Maintenance
     │
     ├─ Create test_unified_login.py (347 lines)
     ├─ Create cleanup_maintenance.py (283 lines)
     └─ Implement 6 test cases
     
[✅] Step 7: Documentation
     │
     ├─ Create IMPLEMENTATION_GUIDE.md
     ├─ Create QUICKSTART.md
     ├─ Create SUMMARY.md
     └─ Create DIAGRAMS.md (this file)

═════════════════════════════════════════════════════════════════
TOTAL: 1,819 lines of production-ready code
STATUS: ✅ COMPLETE - Ready for deployment
═════════════════════════════════════════════════════════════════
```

---

## 7. File Relationships

```
┌─────────────────────────────────────────────────────────────────┐
│                    FILE DEPENDENCY MAP                           │
└─────────────────────────────────────────────────────────────────┘

                    ┌──────────────────┐
                    │   biometric_     │
                    │   auth.db        │
                    │  (SQLite DB)     │
                    └────────┬─────────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
            ▼                ▼                ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ db.py           │ │migrate_unified_ │ │cleanup_         │
│                 │ │login.py         │ │maintenance.py   │
│ - DB access     │ │                 │ │                 │
│ - CRUD ops      │ │ - Create tables │ │ - Show stats    │
│ - 8 new funcs   │ │ - Migrate data  │ │ - Cleanup old   │
│                 │ │ - Verify        │ │ - Aggregate     │
└────────┬────────┘ └─────────────────┘ └─────────────────┘
         │
         │ imported by
         │
         ▼
┌─────────────────┐
│ app.py          │
│                 │
│ - Flask routes  │◄────────┐
│ - /api/login    │         │
│ - Verification  │         │ imported by
│                 │         │
└────────┬────────┘         │
         │                  │
         │ renders      ┌───┴──────────────┐
         │              │ verifier.py      │
         ▼              │                  │
┌─────────────────┐     │ - verify_user()  │
│ templates/      │     │ - 9 methods      │
│ login_unified.  │     │ - Consensus      │
│ html            │     └──────────────────┘
│                 │
│ - Single form   │
│ - Username val. │
│ - Typing timer  │
└─────────────────┘

┌─────────────────┐
│test_unified_    │
│login.py         │
│                 │
│ - 6 test cases  │─────► Sends requests to app.py
│ - Automated     │       /api/login endpoint
└─────────────────┘

DOCUMENTATION FILES (No code dependencies):
┌─────────────────────────────────────────────────────────┐
│ IMPLEMENTATION_GUIDE.md  ◄─── Complete reference        │
│ QUICKSTART.md            ◄─── 3-step guide              │
│ SUMMARY.md               ◄─── Overview                  │
│ DIAGRAMS.md              ◄─── This file (visuals)       │
└─────────────────────────────────────────────────────────┘
```

---

**END OF DIAGRAMS**

These visual diagrams should help understand:
1. ✅ Login flow comparison (Before vs After)
2. ✅ Verification logic step-by-step
3. ✅ Database schema relationships
4. ✅ Security layers
5. ✅ Data retention & cleanup
6. ✅ Implementation timeline
7. ✅ File dependencies

For implementation details, see:
- [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)
- [QUICKSTART.md](QUICKSTART.md)
- [SUMMARY.md](SUMMARY.md)
