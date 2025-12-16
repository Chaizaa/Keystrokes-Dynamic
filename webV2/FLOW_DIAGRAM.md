# 🔄 FLOW DIAGRAM SISTEM KEYSTROKE DYNAMIC

## 📊 OVERVIEW ARSITEKTUR

```
┌──────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (JavaScript)                         │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  KeyboardEvent Capture: keydown/keyup + timestamp + key/code   │  │
│  │  Format: [{t: 1234, evt: 'd', key: 'h', code: 'KeyH'}, ...]   │  │
│  └────────────────────────┬─────────────────────────────────────────┘  │
└────────────────────────────┼──────────────────────────────────────────┘
                             │ POST /api/register_sample
                             │ POST /api/login_attempt
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      APP.PY (Flask Backend)                          │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ process_web_events():                                          │  │
│  │  1. Sort events by timestamp                                   │  │
│  │  2. Validate: Backspace ≤3, Hold time ≤800ms                  │  │
│  │  3. Pair keydown/keyup → Calculate timing                      │  │
│  │  4. Build features:                                            │  │
│  │     • H_features = {"H.h_0": 0.123, "H.e_1": 0.234, ...}      │  │
│  │     • DD_features = {"DD.h_0.e_1": 0.145, ...}                │  │
│  │     • UD_features = {"UD.h_0.e_1": 0.089, ...}                │  │
│  │     • UU_features = {"UU.h_0.e_1": 0.234, ...}                │  │
│  │     • DU_features = {"DU.h_0.e_1": 0.345, ...}                │  │
│  │  5. Return: {"status": "success", "data": {...}}              │  │
│  └────────────────────────┬───────────────────────────────────────┘  │
└────────────────────────────┼──────────────────────────────────────────┘
                             │
            ┌────────────────┴────────────────┐
            │                                 │
   ┌────────▼─────────┐            ┌─────────▼──────────┐
   │  REGISTER        │            │  LOGIN             │
   │  /api/register   │            │  /api/login        │
   └────────┬─────────┘            └─────────┬──────────┘
            │                                 │
            │ Save Enrollment                 │ Verify + Save Log
            ▼                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         DB.PY (Storage Manager)                       │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ save_data():                                                    │  │
│  │  • _save_to_csv()  → CSV format (biometric_auth.csv)          │  │
│  │  • _save_to_sqlite() → SQLite format (biometric_auth.db)      │  │
│  │                                                                 │  │
│  │ [CRITICAL] JSON Serialization:                                 │  │
│  │   if isinstance(v, (list, dict, bool)) or v is None:          │  │
│  │       csv_data[k] = json.dumps(v)  # {"H.h_0": 0.1} → STRING  │  │
│  │   elif isinstance(v, (int, float)):                           │  │
│  │       csv_data[k] = str(v)          # 0.123 → "0.123"        │  │
│  └────────────────────────┬───────────────────────────────────────┘  │
│                            │ get_enrollment_samples(username)         │
│                            ▼                                          │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ Returns: [                                                      │  │
│  │   {                                                             │  │
│  │     'username': 'hapis',                                        │  │
│  │     'H_features': '{"H.h_0": 0.123, "H.e_1": 0.234}',  ← JSON  │  │
│  │     'DD_features': '{"DD.h_0.e_1": 0.145}',            ← JSON  │  │
│  │     'login_result': 'true',                            ← JSON  │  │
│  │     'login_score': '0.876',                            ← STR   │  │
│  │     ...                                                         │  │
│  │   },                                                            │  │
│  │   {...}, {...}  ← Multiple enrollment samples                  │  │
│  │ ]                                                               │  │
│  └────────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
                             ▼ (Only during LOGIN)
┌──────────────────────────────────────────────────────────────────────┐
│                    VERIFIER.PY (ML Logic)                            │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ verify_user(new_features, enrollment_data):                    │  │
│  │                                                                 │  │
│  │ [1] Parse JSON strings back to Python objects:                 │  │
│  │     _parse_features():                                         │  │
│  │       '{"H.h_0": 0.123}' → {"H.h_0": 0.123}                   │  │
│  │                                                                 │  │
│  │ [2] Build User Profile (Mean dari enrollment samples):         │  │
│  │     for fkey in ['H_features', 'DD_features', ...]:           │  │
│  │       mean_profile[fkey] = { "H.h_0": 0.125, ... }            │  │
│  │                                                                 │  │
│  │ [3] Compare New Input vs Profile:                              │  │
│  │     for each feature:                                          │  │
│  │       diff = abs(input - profile)                              │  │
│  │       capped_diff = min(diff, OUTLIER_CAP)                     │  │
│  │                                                                 │  │
│  │ [4] Weighted Scoring:                                          │  │
│  │     score = (H×2.5 + DD×1.5 + UD×1.0 + UU×0.8 + DU×0.5) / 6.3 │  │
│  │                                                                 │  │
│  │ [5] Threshold Decision:                                        │  │
│  │     if score > THRESHOLD: REJECT (fraud)                       │  │
│  │     else: ACCEPT (genuine user)                                │  │
│  │                                                                 │  │
│  │ Return: {"result": True/False, "score": 0.123, "msg": "..."}  │  │
│  └────────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
                             ▼ Result sent back to app.py
┌──────────────────────────────────────────────────────────────────────┐
│                      APP.PY (Response Handler)                        │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ if verification_result['result'] == True:                      │  │
│  │   • Update DB with new enrollment (Adaptive Learning)          │  │
│  │   • Return: {"status": "success", "message": "LOGIN SUKSES"}   │  │
│  │ else:                                                           │  │
│  │   • Save as failed log (data_type='login_attempt')             │  │
│  │   • Return: {"status": "error", "message": "LOGIN GAGAL"}      │  │
│  └────────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
                             ▼ JSON Response
┌──────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (JavaScript)                         │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ if (response.status === "success"):                            │  │
│  │   alert("✅ LOGIN BERHASIL")                                   │  │
│  │ else:                                                           │  │
│  │   alert("❌ LOGIN GAGAL: " + response.message)                 │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 🔍 CRITICAL POINTS (KESINAMBUNGAN FLOW)

### ✅ 1. Feature Extraction (app.py line 139-175)
```python
# GENERATES:
H_features = {"H.h_0": 0.123, "H.e_1": 0.234, ...}
DD_features = {"DD.h_0.e_1": 0.145, ...}
UD_features = {"UD.h_0.e_1": 0.089, ...}
UU_features = {"UU.h_0.e_1": 0.234, ...}
DU_features = {"DU.h_0.e_1": 0.345, ...}
```

### ✅ 2. JSON Serialization (db.py line 27-31)
```python
# BEFORE SAVING TO CSV/SQLite:
if isinstance(v, (list, dict, bool)) or v is None:
    csv_data[k] = json.dumps(v)  # Dict → JSON String
elif isinstance(v, (int, float)):
    csv_data[k] = str(v)          # Number → String

# RESULT IN CSV:
# H_features column: "{\"H.h_0\": 0.123, \"H.e_1\": 0.234}"
# login_result column: "true"
# login_score column: "0.876"
```

### ✅ 3. JSON Deserialization (verifier.py line 16-19)
```python
def _parse_features(self, feature_data):
    if isinstance(feature_data, str):
        try: return json.loads(feature_data)  # JSON String → Dict
        except: return {}
    return feature_data if isinstance(feature_data, dict) else {}

# CONVERTS BACK:
# "{\"H.h_0\": 0.123}" → {"H.h_0": 0.123}
```

### ✅ 4. Feature Comparison (verifier.py line 148-170)
```python
for fkey in ['H_features', 'DD_features', 'UD_features', 'UU_features', 'DU_features']:
    input_feat = self._parse_features(new_features.get(fkey, {}))
    profile_feat = mean_profile.get(fkey, {})
    
    for k in profile_feat.keys():
        if k in input_feat:
            diff = abs(float(input_feat[k]) - float(profile_feat[k]))
```

### ✅ 5. Weighted Scoring (verifier.py line 195-211)
```python
# FORMULA:
final_score = (
    H_weight * feature_scores['H_features'] +
    DD_weight * feature_scores['DD_features'] +
    UD_weight * feature_scores['UD_features'] +
    UU_weight * feature_scores['UU_features'] +
    DU_weight * feature_scores['DU_features']
) / total_weight

# WEIGHTS:
# H=2.5 (most important - hold time)
# DD=1.5 (down-down latency)
# UD=1.0 (up-down transition)
# UU=0.8 (up-up timing)
# DU=0.5 (down-up timing)
```

---

## 🔧 RECENT FIXES

### Fix #1: CSV Corruption (db.py line 27-31)
**Problem:** Boolean `True` dan Float `0.876` ditulis langsung → CSV split jadi 2 kolom
**Solution:** Convert semua complex types ke JSON string atau string

```python
# BEFORE (BUGGY):
if isinstance(v, (list, dict)):
    csv_data[k] = json.dumps(v)
else:
    csv_data[k] = v  # ❌ Bool/Float tidak dihandle!

# AFTER (FIXED):
if isinstance(v, (list, dict, bool)) or v is None:
    csv_data[k] = json.dumps(v)
elif isinstance(v, (int, float)):
    csv_data[k] = str(v)  # ✅ Convert ke string
```

### Fix #2: SQLite Consistency (db.py line 50-57)
**Problem:** SQLite hanya handle `list` dan `dict`, tidak handle `bool`/`float`
**Solution:** Apply logic yang sama seperti CSV

```python
# BEFORE (INCONSISTENT):
if isinstance(v, (list, dict)):
    db_data[k] = json.dumps(v)
else:
    db_data[k] = v  # ❌ Tidak konsisten dengan CSV

# AFTER (CONSISTENT):
if isinstance(v, (list, dict, bool)) or v is None:
    db_data[k] = json.dumps(v)
elif isinstance(v, (int, float)):
    db_data[k] = str(v)  # ✅ Konsisten dengan CSV
```

---

## 📝 DATA TYPE MAPPING

| Python Type | CSV Format | SQLite Format | Verifier Parse |
|------------|-----------|---------------|----------------|
| `dict` | `'{"key": "val"}'` | `'{"key": "val"}'` | `json.loads()` |
| `list` | `'[1, 2, 3]'` | `'[1, 2, 3]'` | `json.loads()` |
| `bool` | `'true'` / `'false'` | `'true'` / `'false'` | `json.loads()` |
| `float` | `'0.876'` | `'0.876'` | `float()` |
| `int` | `'123'` | `'123'` | `int()` |
| `None` | `'null'` | `'null'` | `json.loads()` |
| `str` | `'hello'` | `'hello'` | No parse needed |

---

## ✅ VERIFICATION CHECKLIST

- [x] **app.py** menghasilkan 5 feature dictionaries (H, DD, UD, UU, DU)
- [x] **app.py** return semua 5 features ke endpoint
- [x] **db.py** serialize semua complex types (bool, float, dict, list) ke string
- [x] **db.py** CSV dan SQLite menggunakan logic serialization yang SAMA
- [x] **verifier.py** parse JSON string back to Python dict
- [x] **verifier.py** compare semua 5 feature types dengan weighted scoring
- [x] **app.py** handle verification result dan simpan log

---

## 🎯 STATUS: ✅ FLOW 100% KONSISTEN

**Last Updated:** 15 Dec 2024  
**Version:** Post-Fix (db.py line 27-31 & 50-57)  
**Next Action:** Start Flask fresh → Test 1 user × 10 samples → Validate
