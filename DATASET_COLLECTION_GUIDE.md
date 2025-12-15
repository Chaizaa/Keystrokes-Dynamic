# Dataset Collection Guide for Keystroke Dynamics TA
## Target: Research-Quality Dataset

### Minimum Requirements
- **Users**: 10-15 orang
- **Samples per user**: 
  - 10 enrollment samples (data_type='enrollment')
  - 10 login attempts (data_type='login_attempt')
- **Total samples**: 200-300 minimum

### Ideal Target (for publication-quality research)
- **Users**: 20-30 orang
- **Samples per user**: 15 enrollment + 15 login
- **Total samples**: 600-900

---

## Collection Protocol

### Phase 1: Recruitment (Week 1)
**Target**: 5 users, 100 samples

**Participant Criteria**:
- Familiar dengan keyboard (typing speed minimal)
- Bersedia collect data 2-3 session
- Diverse: berbagai usia, gender, typing skill

**Instructions for Participants**:
```
Halo! Bantu saya collect data untuk penelitian Tugas Akhir tentang 
Keystroke Dynamics (autentikasi berdasarkan cara mengetik).

Langkah:
1. Buka http://127.0.0.1:5000/register (atau IP saya)
2. Masukkan username unik (contoh: nama_anda)
3. Ketik password yang SAMA sebanyak 10 kali
   - Password bebas (min 8 karakter, ada angka/simbol)
   - PENTING: Ketik secara NATURAL seperti biasa
   - Jangan terburu-buru atau terlalu pelan
4. Setelah 10x, pindah ke /login
5. Login dengan username & password yang sama 10 kali

Tips:
- Ketik dengan ritme normal Anda
- Tidak perlu sempurna, backspace OK (max 3x)
- Satu session = 10 enrollment + 10 login (5-7 menit)
```

### Phase 2: Expansion (Week 2-3)
**Target**: 15 users total, 300 samples

**Actions**:
- Recruit teman, keluarga, teman kampus
- Buat Google Form untuk schedule collection
- Track progress per user di spreadsheet

**Quality Control**:
```bash
# Check setiap hari
python validate_dataset.py

# Jika ada user dengan samples < 5, minta tambah data
```

### Phase 3: Final Push (Week 4)
**Target**: 20+ users, 500+ samples

**Diversify**:
- Tambah user dengan typing style berbeda:
  - Fast typers (>60 WPM)
  - Slow typers (<30 WPM)  
  - Hunt-and-peck vs touch typing
- Different devices (laptop keyboard vs external)

---

## Data Quality Checklist

Run after every collection session:

```bash
# 1. Validate
python validate_dataset.py

# 2. Test ML pipeline
python test_pipeline.py

# 3. Check user distribution
python -c "import pandas as pd; df = pd.read_csv('biometric_auth.csv'); print(df['username'].value_counts())"

# 4. Check data types
python -c "import pandas as pd; df = pd.read_csv('biometric_auth.csv'); print(df['data_type'].value_counts())"
```

**Red Flags**:
- User dengan < 5 samples → re-collect
- Samples dengan backspace_count > 5 → exclude dari training
- CSV corruption → fix db.py immediately

---

## Progress Tracking Template

```
Date: ___________
Users collected today: ___
Total users: ___ / 20
Total samples: ___ / 500

Issues encountered:
- 
- 

Action items:
- 
- 
```

---

## Backup Strategy

**PENTING**: Backup CSV setiap hari!

```bash
# Manual backup
Copy-Item biometric_auth.csv "backups/backup_$(Get-Date -Format 'yyyy-MM-dd').csv"

# Atau otomatis via Git
git add biometric_auth.csv
git commit -m "Data collection: $(Get-Date -Format 'yyyy-MM-dd')"
git push
```

---

## Timeline Estimate

| Week | Target Users | Target Samples | Time Investment |
|------|--------------|----------------|-----------------|
| 1    | 5            | 100            | 3-5 hours       |
| 2    | 10           | 200            | 5-7 hours       |
| 3    | 15           | 300            | 3-5 hours       |
| 4    | 20+          | 500+           | 2-3 hours       |

**Total**: ~15-20 hours over 1 month

---

## Remote Collection (Optional)

Jika mau collect remote (participants di lokasi berbeda):

1. Deploy Flask ke server:
   ```bash
   # Heroku, Railway, atau Azure App Service
   # Atau ngrok untuk quick sharing:
   ngrok http 5000
   ```

2. Share link ke participants dengan instructions

3. Monitor real-time:
   ```bash
   tail -f biometric_auth.csv
   ```

**Security Note**: For TA/research purposes, clear-text passwords in DB OK. 
For production, NEVER do this!

---

## Success Criteria

✅ **Minimal untuk lulus TA**:
- 10 users
- 150+ total samples
- No major data corruption
- Basic ML model accuracy >70%

✅ **Ideal untuk publikasi**:
- 20+ users
- 400+ total samples  
- Data quality score >80%
- ML model accuracy >85%

Good luck! 🚀
