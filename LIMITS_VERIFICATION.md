# Frontend & Backend Limits - Verification Report

## ✅ Fixes Applied for 10x Registration + 10x Login

### **1. Frontend - register.html**
**Line 112**: Changed `targetSamples = 2` → `targetSamples = 10`
- User dapat submit hingga 10 enrollment samples
- Progress counter: "0 / 10" → "10 / 10"
- Auto-redirect ke home setelah 10 samples

**Status**: ✅ FIXED

---

### **2. Frontend - login.html**
**No limit found** - User dapat login unlimited times
- Tidak ada counter atau batasan jumlah login attempts
- Setiap login dikirim ke backend untuk verifikasi
- Data tersimpan dengan `data_type='login_attempt'`

**Status**: ✅ Already OK (no changes needed)

---

### **3. Backend - app.py**
**Line 271**: Updated minimum enrollment check
- OLD: `if len(enrollment_data) < 2` 
- NEW: `if len(enrollment_data) < 5`
- Pesan error: Sekarang menampilkan jumlah sampel yang dimiliki user

**Reason**: Untuk research-quality data, minimal 5 enrollment samples lebih baik untuk statistical profiling

**Status**: ✅ FIXED

---

### **4. Database - db.py**
**Line 95**: Removed LIMIT 10 from enrollment query
- OLD: `ORDER BY id DESC LIMIT 10`
- NEW: `ORDER BY id DESC` (no limit)
- Fungsi sekarang: Ambil SEMUA enrollment samples per user

**Reason**: 
- Untuk ML training, semakin banyak data semakin baik
- Statistical verification (verifier.py) akan gunakan semua samples untuk build profile
- User dengan 15-20 enrollment samples → better accuracy

**Status**: ✅ FIXED

---

### **5. Statistical Verifier - verifier.py**
**No changes needed**
- `verify_user()` sudah support multiple enrollment samples (no hardcoded limit)
- Automatically calculates mean/std from ALL provided samples
- Works dengan 2 samples, 10 samples, atau 100 samples

**Status**: ✅ Already OK

---

## Current System Behavior

### Registration Flow (10x enrollment):
```
User visits /register
↓
Enter username + password
↓
Submit 10 times (frontend counter: 0→10)
↓
Each submit → POST /api/register_sample
↓
Backend saves to CSV + SQLite with data_type='enrollment'
↓
After 10 samples → Auto-redirect to home
```

### Login Flow (unlimited attempts):
```
User visits /login
↓
Enter username + password
↓
Submit (no limit, can do 10x, 20x, etc.)
↓
POST /api/login_attempt
↓
Backend:
  - Checks if user has ≥5 enrollment samples
  - If YES → verify_user() against enrollment profile
  - If NO → Error: "Need 5+ enrollment samples"
↓
Save login attempt with data_type='login_attempt'
↓
Return verification result
```

---

## Data Collection Workflow

### Recommended Protocol:
1. **Registration Phase** (per user):
   - Complete all 10 enrollment samples
   - DO NOT stop midway
   - Ensure same password every time
   - Type naturally (not too fast/slow)

2. **Login Phase** (per user):
   - After 10 enrollments complete
   - Attempt 10 login tries
   - Can be done in same session or later
   - Each attempt is verified against enrollment profile

3. **Dataset Result**:
   - Per user: 10 enrollment + 10 login = 20 samples
   - 10 users: 200 samples total
   - 20 users: 400 samples total

---

## Validation Commands

### Check current limits:
```bash
# Frontend registration limit
grep "targetSamples" webV2/templates/register.html
# Should show: const targetSamples = 10;

# Backend enrollment minimum
grep "len(enrollment_data)" webV2/app.py
# Should show: if len(enrollment_data) < 5:

# Database query limit
grep "LIMIT" webV2/db.py | grep enrollment
# Should show: No results (LIMIT removed)
```

### Test collection:
```bash
# 1. Start server
python app.py

# 2. Open browser
http://127.0.0.1:5000/register

# 3. Register user with 10 samples
# 4. Login 10 times

# 5. Check database
python -c "import pandas as pd; df = pd.read_csv('biometric_auth.csv'); print(df[['username', 'data_type']].value_counts())"
```

---

## Database Structure Per User

| Sample # | data_type   | Purpose               | Used For        |
|----------|-------------|-----------------------|-----------------|
| 1-10     | enrollment  | Profile building      | Statistical baseline, ML training |
| 11-20    | login_attempt | Verification tests  | ML testing, accuracy metrics |

**Note**: 
- `enrollment` samples: Build user's typing profile (mean, std)
- `login_attempt` samples: Test authentication accuracy

---

## ML Training Implications

### With 10 enrollment samples per user:
- Better statistical profile (mean & std more accurate)
- Less variance in verification scores
- Improved EER (Equal Error Rate)
- Fewer false positives/negatives

### With 10 login attempts per user:
- Robust testing dataset
- Can calculate FAR (False Accept Rate)
- Can calculate FRR (False Reject Rate)
- Cross-validation possible

---

## Next Steps

1. ✅ Limits configured (10 enrollment + unlimited login)
2. ✅ Backend minimum check (5 samples)
3. ✅ Database supports unlimited storage
4. ⏳ **START DATA COLLECTION**
5. ⏳ Validate with `python validate_dataset.py`
6. ⏳ Test ML pipeline with `python test_pipeline.py`

---

## Testing Checklist

- [ ] Register 1 user with 10 samples → Success?
- [ ] Try login with < 5 samples → Should get error
- [ ] Complete 10 enrollments, then login 10x → All verified?
- [ ] Check CSV: 20 rows for user (10 enrollment + 10 login)?
- [ ] Run validator: No corruption?
- [ ] Test ML pipeline: Feature matrix builds correctly?

---

**Status**: 🟢 All systems ready for 10x10 data collection protocol
**Recommendation**: Begin Phase 1 collection with 5 users (100 samples)
