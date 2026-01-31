# 🚀 Quick Start Guide - Hybrid Mode System

## 📋 Overview

Sistem sekarang punya **2 MODE** di halaman login:
1. **Collection Mode** → Simpan 10 login samples (untuk dataset)
2. **Verification Mode** → Test autentikasi biometrik (tanpa save)

---

## 🎯 Mode 1: Collection Mode (Dataset)

**Tujuan:** Kumpulkan 10 login samples per user untuk thesis dataset

**Langkah:**
1. Buka http://127.0.0.1:5000/login
2. Pilih **"📊 Collection Mode"** (biru)
3. Masukkan username & password
4. Klik **"Mulai Pengumpulan Data"**
5. Ketik password 10x (tekan ENTER setiap kali)
6. Lihat quality feedback real-time!

**Quality Feedback:**
- `GOOD (100/100)` → Perfect, consistent typing
- `QUESTIONABLE (70/100)` → Some irregularities (e.g., long pauses)
- `POOR (40/100)` → Many issues (e.g., super fast/slow typing)

**Output:**
- Data disimpan ke `biometric_auth.csv`
- 42 kolom dengan statistical features
- Quality metrics: `quality_label`, `quality_score`, `quality_warnings`

---

## 🔐 Mode 2: Verification Mode (Testing)

**Tujuan:** Test biometric authentication tanpa save data

**Langkah:**
1. Pastikan user sudah punya **minimal 5 enrollment samples** (dari halaman register)
2. Buka http://127.0.0.1:5000/login
3. Pilih **"🔐 Verification Mode"** (biru)
4. Masukkan username & password
5. Klik **"Mulai Verifikasi"**
6. Ketik password 1x (tekan ENTER)
7. Lihat hasil verification!

**Hasil Verifikasi:**
- ✅ **LOGIN SUKSES** (hijau) → Biometrik cocok
  - Score: 85.3
  - Detail: "Inlier ratio: 82%"
- ❌ **LOGIN GAGAL** (merah) → Biometrik tidak cocok
  - Score: 45.2
  - Detail: "Too many outliers"

**Catatan:** Data TIDAK disimpan di mode verification (pure testing)

---

## 📊 Dataset Collection Strategy

### Per User:
- **Register page:** 10 enrollment samples (data_type='enrollment')
- **Login page (Collection Mode):** 10 login samples (data_type='login')
- **Total:** 20 samples per user

### Target Event:
- **150 users × 20 samples = 3000 samples**
- Bisa pake `check_dataset_progress.py` untuk monitoring

---

## 🔬 New Features in CSV

### Statistical Features (20 columns):
```
H_mean, H_std, H_min, H_max
DD_mean, DD_std, DD_min, DD_max
UD_mean, UD_std, UD_min, UD_max
UU_mean, UU_std, UU_min, UU_max
DU_mean, DU_std, DU_min, DU_max
```

### Advanced Features (8 columns):
```
rollover_frequency   → Count of key overlaps
error_rate           → Backspace ratio
typing_speed         → Chars per second
H_cv, DD_cv, UD_cv, UU_cv, DU_cv  → Consistency metrics
```

### Quality Metrics (3 columns):
```
quality_label        → 'good', 'questionable', 'poor'
quality_score        → 0-100
quality_warnings     → JSON array of issues
```

---

## 🧪 Testing Checklist

### Test Collection Mode:
- [ ] Buka http://127.0.0.1:5000/login
- [ ] Pilih Collection Mode
- [ ] Input username: `testuser`, password: `password123`
- [ ] Ketik 10x, cek quality feedback muncul
- [ ] Cek `biometric_auth.csv` ada 10 rows dengan `data_type='login'`
- [ ] Cek ada 42 kolom (statistical features, quality metrics)

### Test Verification Mode:
- [ ] Register dulu di http://127.0.0.1:5000/register (10 enrollment samples)
- [ ] Balik ke login, pilih Verification Mode
- [ ] Ketik password dengan **pola yang sama**
- [ ] Cek muncul ✅ LOGIN SUKSES
- [ ] Ketik password dengan **pola berbeda** (pause lama, typo, dll)
- [ ] Cek muncul ❌ LOGIN GAGAL

### Test Quality Assessment:
- [ ] Sengaja ketik dengan pause lama (> 2 detik)
- [ ] Cek warning muncul: "Long pauses detected"
- [ ] Sengaja ketik super cepat (spam keyboard)
- [ ] Cek warning muncul: "Unusually fast typing"
- [ ] Ketik dengan rollover banyak (tekan 2 keys sekaligus)
- [ ] Cek warning muncul: "Very high rollover rate"

---

## 📈 Monitoring

### Real-time Progress:
```bash
python check_dataset_progress.py
```

Output:
```
╔════════════════════════════════════════════════╗
║      KEYSTROKE DATASET COLLECTION PROGRESS     ║
╚════════════════════════════════════════════════╝

Target: 3000 samples (150 users × 20 samples)

█████████████░░░░░░░░░░░░░░░░░  30.0%

CURRENT STATUS:
Total samples: 900 / 3000
Enrollment samples: 450
Login samples: 450
Total users: 45

PER-USER BREAKDOWN:
testuser - Enrollment: 10, Login: 10 [COMPLETE]
...
```

---

## 🎓 For Thesis Demo

### Scenario 1: Dataset Collection
1. Show Collection Mode
2. Collect 10 samples with quality feedback
3. Show CSV with statistical features
4. Explain quality assessment system

### Scenario 2: Biometric Verification
1. Show Verification Mode
2. Demo successful authentication (consistent typing)
3. Demo failed authentication (different rhythm)
4. Explain verification logic (statistical distance)

### Scenario 3: Quality Analysis
1. Show sample with `quality_label='good'`
2. Show sample with `quality_label='poor'`
3. Explain quality warnings
4. Show filtering strategy for ML training

---

## 🔧 Troubleshooting

### Error: "User belum terdaftar atau data enrollment kurang"
**Solusi:** User harus register dulu (minimal 5 enrollment samples) sebelum bisa verify

### Error: "Too many outliers"
**Solusi:** Ketik dengan pola yang lebih consistent (sama kayak enrollment)

### Warning: "Long pauses detected"
**Solusi:** Ketik tanpa pause lama, fokus ke rhythm yang consistent

### Warning: "High timing variance"
**Solusi:** Ketik dengan speed yang lebih consistent (jangan cepat-lambat)

---

## 🎉 Ready to Use!

Semua fitur sudah terimplementasi dan siap digunakan:
- ✅ Hybrid mode (Collection + Verification)
- ✅ Statistical features (20 columns)
- ✅ Advanced features (8 columns)
- ✅ Quality assessment (real-time)
- ✅ No import errors
- ✅ Flask running successfully

**Flask URL:** http://127.0.0.1:5000

**Pages:**
- Home: http://127.0.0.1:5000/
- Register: http://127.0.0.1:5000/register
- Login (Hybrid): http://127.0.0.1:5000/login

**Happy collecting! 🚀**
