# 🚀 Quick Start - Unified Login System

## 📦 What's New?

**Single unified login** menggantikan dual-mode (Collection vs Verification):
- ✅ Otomatis verify setiap login
- ✅ Hanya simpan genuine user data
- ✅ Failed logins TANPA keystroke data
- ✅ Rate limiting (5 attempts/15 min)
- ✅ Clean database separation

---

## ⚡ 3-Step Quick Start

### 1️⃣ Backup & Migrate Database
```bash
cd webV2
python migrate_unified_login.py
```

✅ Expected: 4 tabel baru (`enrollment_vectors`, `verified_logins`, `failed_logins`, `login_statistics`)

### 2️⃣ Test System
```bash
# Terminal 1: Start Flask
python app.py

# Terminal 2: Run tests
python test_unified_login.py
```

✅ Expected: `6/6 tests passed (100%)`

### 3️⃣ Try New Login UI
```
http://localhost:5000/login
```

✅ Expected: Single clean login form (no mode selection)

---

## 📁 Files Created/Modified

| File | Status | Purpose |
|------|--------|---------|
| `webV2/migrate_unified_login.py` | ✅ NEW | Database migration |
| `webV2/db.py` | ✅ MODIFIED | +8 functions (230 lines) |
| `webV2/app.py` | ✅ MODIFIED | +`/api/login` endpoint (181 lines) |
| `webV2/templates/login_unified.html` | ✅ NEW | Simplified UI (495 lines) |
| `webV2/test_unified_login.py` | ✅ NEW | Test suite (347 lines) |
| `webV2/cleanup_maintenance.py` | ✅ NEW | DB maintenance (283 lines) |
| `IMPLEMENTATION_GUIDE.md` | ✅ NEW | Full documentation |

**Total: 1,819 lines of new code**

---

## 🎯 Key Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/login` | GET | **NEW** Unified login UI |
| `/login/legacy` | GET | ARCHIVED - legacy dual-mode UI removed |
| `/api/login` | POST | **NEW** Unified login endpoint |
| `/api/login_attempt` | POST | LEGACY verification endpoint |

---

## 🔧 Maintenance Commands

```bash
# Show database statistics
python cleanup_maintenance.py

# Cleanup old data + aggregate stats
python cleanup_maintenance.py --all

# Run tests
python test_unified_login.py
```

---

## 📊 Database Structure

```
Before:                    After:
┌─────────────┐           ┌──────────────────┐
│user_vectors │           │enrollment_vectors│ (20 samples/user)
│(mixed data) │    →      ├──────────────────┤
└─────────────┘           │verified_logins   │ (genuine only)
                          ├──────────────────┤
                          │failed_logins     │ (no keystroke)
                          ├──────────────────┤
                          │login_statistics  │ (daily aggregate)
                          └──────────────────┘
```

---

## ⚠️ Breaking Changes

1. **Default login route changed:**
   - Before: `/login` → `login.html` (dual-mode)
   - After: `/login` → `login_unified.html` (single-mode)
   - Legacy: `/login/legacy` → ARCHIVED (removed); use `/login` (unified)

2. **New database schema:**
   - Run migration script before using
   - Old `user_vectors` table still exists (backward compat)

3. **API response format:**
   - `/api/login` returns different JSON structure
   - Use `/api/login_attempt` for legacy apps

---

## 🐛 Troubleshooting

**Migration fails?**
```bash
# Check if DB is locked
sqlite3 biometric_auth.db "PRAGMA integrity_check"
```

**Tests fail?**
```bash
# Ensure test user has enrollment complete (20 samples)
sqlite3 biometric_auth.db "SELECT COUNT(*) FROM enrollment_vectors WHERE username='test_unified_user'"
```

**Rate limited?**
```bash
# Clear failed logins
sqlite3 biometric_auth.db "DELETE FROM failed_logins WHERE username='your_username'"
```

---

## 📚 Full Documentation

See [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) for:
- Complete API reference
- Security features
- Database schema details
- Rollback procedures
- Future enhancements

---

## ✅ Success Criteria

After implementation, you should see:

- [x] `/login` shows new unified UI (no mode selection)
- [x] Login verifies authenticity BEFORE saving
- [x] Failed logins logged without keystroke data
- [x] Rate limiting works (5 attempts/15 min)
- [x] Database has 4 new tables
- [x] Test suite passes 6/6 tests
- [x] Maintenance script shows statistics

---

**Ready to go! 🚀**

Questions? Check `IMPLEMENTATION_GUIDE.md` or open an issue.
