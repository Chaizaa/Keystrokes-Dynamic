# 🚀 CARA START FLASK FRESH (Tanpa Error)

## ✅ CHECKLIST SEBELUM START

### 1️⃣ Kill Semua Python Processes (WAJIB!)
```powershell
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
```
**Kenapa?** Kalau ada Flask lama masih jalan, dia pakai kode lama yang masih bug.

---

### 2️⃣ Backup & Delete Database Lama (Opsional tapi Recommended)
```powershell
# Kalau mau backup dulu (opsional):
Copy-Item biometric_auth.csv biometric_auth_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').csv -ErrorAction SilentlyContinue
Copy-Item biometric_auth.db biometric_auth_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').db -ErrorAction SilentlyContinue

# Delete database lama (FRESH START):
Remove-Item biometric_auth.csv -ErrorAction SilentlyContinue
Remove-Item biometric_auth.db -ErrorAction SilentlyContinue
```
**Kenapa?** Data lama mungkin corrupt. Start fresh = 100% clean.

---

### 3️⃣ Verify db.py Sudah Fix (CRITICAL!)
Buka `db.py` line 20-30, pastikan ada:
```python
if isinstance(v, (list, dict, bool)) or v is None:
    csv_data[k] = json.dumps(v)
elif isinstance(v, (int, float)):
    csv_data[k] = str(v)
```
**Kalau masih cuma `if isinstance(v, (list, dict))` → BELUM FIX!**

---

### 4️⃣ Start Flask
```powershell
cd C:\Users\Hafidz\Desktop\Keystrokes-Dynamic\webV2
python app.py
```

Tunggu sampai muncul:
```
 * Running on http://127.0.0.1:5000
```

---

## ✅ VALIDATION TEST (PENTING!)

### 5️⃣ Collect 1 User Test (10 Samples)
1. Buka: http://127.0.0.1:5000/register
2. Username: `testuser`
3. Password: `hello123!` (10x)
4. Pastikan progress bar 0/10 → 10/10 ✅

---

### 6️⃣ Check File Integrity
```powershell
# Lihat jumlah baris CSV (harus 11 = 1 header + 10 data):
(Get-Content biometric_auth.csv).Count

# Check error dengan validator:
python validate_dataset.py
```

**Expected Output:**
```
✅ CSV file loaded successfully: 10 samples
✅ All columns present
✅ All JSON columns parseable
✅ No corruption detected
```

**Kalau masih ada error "Expected 19 fields, saw 21" → ada yang salah, JANGAN lanjut!**

---

## 🔴 TROUBLESHOOTING

### Error: "Address already in use"
```powershell
# Kill semua Python lagi:
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force

# Tunggu 3 detik, lalu start lagi:
Start-Sleep -Seconds 3
python app.py
```

---

### Error: "Expected 19 fields, saw 21"
```powershell
# Check db.py line 27-30, pastikan handle bool/float:
Get-Content db.py | Select-Object -Index 26..29
```

Harus ada: `isinstance(v, (list, dict, bool))` dan `isinstance(v, (int, float))`

---

### Error: "Permission denied" (CSV)
File CSV masih kebuka di Excel/Notepad. **Tutup semua aplikasi yang buka CSV**, lalu:
```powershell
Remove-Item biometric_auth.csv -Force
python app.py
```

---

## 📋 QUICK COMMAND CHEATSHEET

```powershell
# [1] Kill Python + Delete DB + Start Fresh:
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force; Remove-Item biometric_auth.* -ErrorAction SilentlyContinue; python app.py

# [2] Validate Dataset (cepat):
python validate_dataset.py

# [3] Check berapa sample:
(Get-Content biometric_auth.csv).Count

# [4] Lihat 3 baris pertama CSV:
Get-Content biometric_auth.csv | Select-Object -First 3
```

---

## 🎯 GOLDEN RULE

**SELALU LAKUKAN VALIDATION TEST DULU (1 user × 10 samples) SEBELUM COLLECT DATA BANYAK!**

Kalau test 10 samples ✅ bersih → baru lanjut collect full dataset.

Kalau test 10 samples ❌ corrupt → fix dulu, JANGAN LANJUT!

---

**Generated:** 15 Dec 2024  
**Status:** ✅ db.py FIXED (handle bool/float)  
**Next Step:** Follow checklist di atas → Validate → Collect full dataset
