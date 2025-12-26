# 📚 Penjelasan Lengkap Fitur Keystroke Dynamics

**Sistem Biometrik Berbasis Pola Ketikan Keyboard**

---

## 📖 Daftar Isi

1. [Raw Vectors (Vektor Mentah)](#1-raw-vectors-vektor-mentah)
2. [Labeled Features (Fitur Berlabel)](#2-labeled-features-fitur-berlabel)
3. [Statistical Features (Fitur Statistik)](#3-statistical-features-fitur-statistik)
4. [Advanced Features (Fitur Lanjutan)](#4-advanced-features-fitur-lanjutan)
5. [Quality Metrics (Metrik Kualitas)](#5-quality-metrics-metrik-kualitas)
6. [Contoh Data Lengkap](#6-contoh-data-lengkap)

---

## 1. Raw Vectors (Vektor Mentah)

### 📝 Definisi

Raw vectors adalah **data timing mentah** yang diambil langsung dari keystroke events. Data ini merupakan representasi dasar dari pola ketikan user.

### 🔢 5 Jenis Vektor

#### 1.1 H Vector (Hold Time) ✅ FITUR ORIGINAL
**Apa itu?** Waktu dari tombol ditekan (keydown) sampai dilepas (keyup) untuk **setiap karakter**.

> 💡 **Catatan:** Fitur ini **sudah ada sejak awal** (original code). H Vector adalah fondasi dari keystroke dynamics.

**Rumus:**
```
H[i] = keyup_time[i] - keydown_time[i]
```

**Contoh:**
Ketik password: `password`

| Karakter | Keydown | Keyup | H (detik) |
|----------|---------|-------|-----------|
| p | 0.000 | 0.120 | 0.120 |
| a | 0.250 | 0.380 | 0.130 |
| s | 0.500 | 0.610 | 0.110 |
| s | 0.750 | 0.870 | 0.120 |
| w | 1.000 | 1.140 | 0.140 |
| o | 1.250 | 1.360 | 0.110 |
| r | 1.500 | 1.620 | 0.120 |
| d | 1.750 | 1.880 | 0.130 |

**H_vector:**
```python
[0.120, 0.130, 0.110, 0.120, 0.140, 0.110, 0.120, 0.130]
# Total: 8 nilai (sesuai jumlah karakter)
```

**Interpretasi:**
- **0.120 detik** = User menahan tombol 'p' selama 120ms
- Nilai kecil (< 0.1s) = Ketikan cepat/ringan
- Nilai besar (> 0.2s) = Ketikan lambat/berat

---

#### 1.2 DD Vector (Down-Down Time) ✅ FITUR ORIGINAL
**Apa itu?** Waktu dari tombol pertama ditekan sampai tombol berikutnya ditekan.

> 💡 **Catatan:** Fitur ini **sudah ada sejak awal** (original code). DD Vector menangkap typing rhythm.

**Rumus:**
```
DD[i] = keydown_time[i+1] - keydown_time[i]
```

**Contoh:**
| Transisi | Keydown_1 | Keydown_2 | DD (detik) |
|----------|-----------|-----------|------------|
| p → a | 0.000 | 0.250 | 0.250 |
| a → s | 0.250 | 0.500 | 0.250 |
| s → s | 0.500 | 0.750 | 0.250 |
| s → w | 0.750 | 1.000 | 0.250 |
| w → o | 1.000 | 1.250 | 0.250 |
| o → r | 1.250 | 1.500 | 0.250 |
| r → d | 1.500 | 1.750 | 0.250 |

**DD_vector:**
```python
[0.250, 0.250, 0.250, 0.250, 0.250, 0.250, 0.250]
# Total: 7 nilai (n-1 transisi)
```

**Interpretasi:**
- **0.250 detik** = Jarak waktu antar tombol (typing rhythm)
- DD konsisten = Typing rhythm stabil
- DD variatif = Typing rhythm tidak teratur

---

#### 1.3 UD Vector (Up-Down Time) 🆕 FITUR BARU
**Apa itu?** Waktu dari tombol pertama dilepas (keyup) sampai tombol berikutnya ditekan (keydown).

> 🚀 **Catatan:** Fitur ini **DITAMBAHKAN BARU** untuk deteksi rollover (key overlap). UD negatif = rollover!

**Rumus:**
```
UD[i] = keydown_time[i+1] - keyup_time[i]
```

**Contoh:**
| Transisi | Keyup_1 | Keydown_2 | UD (detik) |
|----------|---------|-----------|------------|
| p → a | 0.120 | 0.250 | 0.130 |
| a → s | 0.380 | 0.500 | 0.120 |
| s → s | 0.610 | 0.750 | 0.140 |
| s → w | 0.870 | 1.000 | 0.130 |
| w → o | 1.140 | 1.250 | 0.110 |
| o → r | 1.360 | 1.500 | 0.140 |
| r → d | 1.620 | 1.750 | 0.130 |

**UD_vector:**
```python
[0.130, 0.120, 0.140, 0.130, 0.110, 0.140, 0.130]
```

**⚠️ PENTING: Rollover Detection**

Jika UD **negatif**, artinya ada **key overlap** (rollover):

| Transisi | Keyup_1 | Keydown_2 | UD (detik) |
|----------|---------|-----------|------------|
| p → a | 0.120 | 0.100 | **-0.020** ← ROLLOVER! |

**Interpretasi:**
- **UD > 0** = Tombol dilepas dulu, baru tekan tombol berikutnya (normal)
- **UD < 0** = Tombol kedua ditekan sebelum tombol pertama dilepas (overlap/rollover)
- **Rollover** = Ciri khas touch typing yang cepat!

---

#### 1.4 UU Vector (Up-Up Time) 🆕 FITUR BARU
**Apa itu?** Waktu dari tombol pertama dilepas sampai tombol berikutnya dilepas.

> 🚀 **Catatan:** Fitur ini **DITAMBAHKAN BARU** untuk menangkap full cycle antar tombol.

**Rumus:**
```
UU[i] = keyup_time[i+1] - keyup_time[i]
```

**Contoh:**
| Transisi | Keyup_1 | Keyup_2 | UU (detik) |
|----------|---------|---------|------------|
| p → a | 0.120 | 0.380 | 0.260 |
| a → s | 0.380 | 0.610 | 0.230 |
| s → s | 0.610 | 0.870 | 0.260 |
| s → w | 0.870 | 1.140 | 0.270 |
| w → o | 1.140 | 1.360 | 0.220 |
| o → r | 1.360 | 1.620 | 0.260 |
| r → d | 1.620 | 1.880 | 0.260 |

**UU_vector:**
```python
[0.260, 0.230, 0.260, 0.270, 0.220, 0.260, 0.260]
```

**Interpretasi:**
- UU menggambarkan **keseluruhan cycle** dari satu tombol ke tombol berikutnya
- Mirip dengan DD tapi memperhitungkan waktu hold time

---

#### 1.5 DU Vector (Down-Up Time) 🆕 FITUR BARU
**Apa itu?** Waktu dari tombol pertama ditekan sampai tombol berikutnya dilepas.

> 🚀 **Catatan:** Fitur ini **DITAMBAHKAN BARU** untuk menangkap full span waktu antar tombol.

**Rumus:**
```
DU[i] = keyup_time[i+1] - keydown_time[i]
```

**Contoh:**
| Transisi | Keydown_1 | Keyup_2 | DU (detik) |
|----------|-----------|---------|------------|
| p → a | 0.000 | 0.380 | 0.380 |
| a → s | 0.250 | 0.610 | 0.360 |
| s → s | 0.500 | 0.870 | 0.370 |
| s → w | 0.750 | 1.140 | 0.390 |
| w → o | 1.000 | 1.360 | 0.360 |
| o → r | 1.250 | 1.620 | 0.370 |
| r → d | 1.500 | 1.880 | 0.380 |

**DU_vector:**
```python
[0.380, 0.360, 0.370, 0.390, 0.360, 0.370, 0.380]
```

**Interpretasi:**
- DU menggambarkan **span waktu** dari awal tombol pertama sampai selesai tombol kedua
- Berguna untuk mendeteksi pola "motor planning" (perencanaan gerakan)

---

### 🎯 Kenapa 5 Vektor? Kenapa Bukan Cuma H dan DD?

**Penelitian Klasik (Monrose & Rubin, 2000):**
- Hanya pakai **H + DD** (2 vektor)
- Akurasi: ~75%

**Penelitian Modern (Killourhy, 2009):**
- Pakai **H + DD + UD** (3 vektor)
- Akurasi: ~85%

**Sistem Kita:**
- Pakai **H + DD + UD + UU + DU** (5 vektor)
- Akurasi target: **90%+**
- **Alasan:** Lebih banyak informasi = Lebih banyak pola unik = Lebih akurat!

---

### 📊 Status Fitur Raw Vectors

| Vektor | Status | Keterangan |
|--------|--------|------------|
| **H (Hold Time)** | ✅ **ORIGINAL** | Sudah ada sejak awal |
| **DD (Down-Down)** | ✅ **ORIGINAL** | Sudah ada sejak awal |
| **UD (Up-Down)** | 🆕 **BARU** | Ditambahkan untuk deteksi rollover |
| **UU (Up-Up)** | 🆕 **BARU** | Ditambahkan untuk full cycle |
| **DU (Down-Up)** | 🆕 **BARU** | Ditambahkan untuk full span |

---

## 2. Labeled Features (Fitur Berlabel) 🆕 FITUR BARU

### 📝 Definisi

Labeled features adalah **raw vectors yang diberi label karakter dan posisi**. Ini membuat sistem bisa mengenali pola ketikan untuk **kombinasi karakter spesifik**.

> 🚀 **Catatan:** Fitur ini **DITAMBAHKAN BARU** untuk memberikan context-awareness pada ML model. Original code hanya menyimpan raw vectors tanpa label karakter.

### 🔤 Format

```
H.{karakter}_{posisi} = waktu_hold
DD.{karakter_1}_{posisi_1}.{karakter_2}_{posisi_2} = waktu_transisi
```

### 📊 Contoh Lengkap

Password: `pass`

#### H_features (Hold Time dengan Label)
```json
{
  "H.p_0": 0.120,  // Tombol 'p' di posisi 0, hold 120ms
  "H.a_1": 0.130,  // Tombol 'a' di posisi 1, hold 130ms
  "H.s_2": 0.110,  // Tombol 's' di posisi 2, hold 110ms
  "H.s_3": 0.120   // Tombol 's' di posisi 3, hold 120ms
}
```

#### DD_features (Down-Down dengan Label)
```json
{
  "DD.p_0.a_1": 0.250,  // Dari 'p' ke 'a', jarak 250ms
  "DD.a_1.s_2": 0.240,  // Dari 'a' ke 's', jarak 240ms
  "DD.s_2.s_3": 0.260   // Dari 's' ke 's', jarak 260ms
}
```

#### UD_features (Up-Down dengan Label)
```json
{
  "UD.p_0.a_1": 0.130,   // Lepas 'p' → Tekan 'a', jeda 130ms
  "UD.a_1.s_2": 0.110,   // Lepas 'a' → Tekan 's', jeda 110ms
  "UD.s_2.s_3": -0.020   // Lepas 's' → Tekan 's', OVERLAP 20ms!
}
```

**🎯 Interpretasi Rollover:**
- `UD.s_2.s_3 = -0.020` → User mengetik 's' kedua sebelum 's' pertama dilepas!
- Ini adalah **ciri khas biometrik** dari typing style!

#### UU_features (Up-Up dengan Label)
```json
{
  "UU.p_0.a_1": 0.260,
  "UU.a_1.s_2": 0.230,
  "UU.s_2.s_3": 0.240
}
```

#### DU_features (Down-Up dengan Label)
```json
{
  "DU.p_0.a_1": 0.380,
  "DU.a_1.s_2": 0.350,
  "DU.s_2.s_3": 0.360
}
```

### ✨ Keuntungan Labeled Features

**1. Context-Aware (Sadar Konteks)**
```python
# Sistem bisa membedakan:
H.a_1 = 0.130  # 'a' di posisi 1 (setelah 'p')
H.a_5 = 0.150  # 'a' di posisi 5 (setelah huruf lain)
# User mungkin mengetik 'a' dengan speed berbeda tergantung posisi!
```

**2. Character-Specific Patterns (Pola Per Karakter)**
```python
# Sistem bisa mengenali:
DD.a_1.s_2 = 0.240  # Transisi 'a' ke 's' (jari tengah → jari manis)
DD.s_2.d_3 = 0.280  # Transisi 's' ke 'd' (jari manis → jari tengah)
# Jarak antar jari berbeda = timing berbeda!
```

**3. Machine Learning dengan Features Engineering**
```python
# Bisa dipakai untuk:
- Random Forest (tree-based features)
- Neural Networks (input layer dengan dimensi tetap)
- Support Vector Machine (kernel tricks dengan features)
```

---

## 3. Statistical Features (Fitur Statistik) 🆕 FITUR BARU

### 📝 Definisi

Statistical features adalah **ringkasan statistik** dari raw vectors. Ini mengubah data dengan panjang variabel menjadi **fixed-size features** (ukuran tetap).

> 🚀 **Catatan:** Fitur ini **DITAMBAHKAN BARU** untuk menghasilkan fixed-size features yang kompatibel dengan algoritma ML tradisional (Random Forest, SVM, dll). Original code hanya menyimpan raw vectors dengan panjang variabel.

### 📊 4 Statistik Per Vektor

| Statistik | Rumus | Interpretasi |
|-----------|-------|--------------|
| **Mean** | Rata-rata | Baseline kecepatan |
| **Std Dev** | Standar deviasi | Konsistensi (kecil = konsisten) |
| **Min** | Nilai terkecil | Kecepatan maksimal |
| **Max** | Nilai terbesar | Kecepatan minimal |

### 🔢 Total: 20 Features

```
H_mean, H_std, H_min, H_max      (4 features)
DD_mean, DD_std, DD_min, DD_max  (4 features)
UD_mean, UD_std, UD_min, UD_max  (4 features)
UU_mean, UU_std, UU_min, UU_max  (4 features)
DU_mean, DU_std, DU_min, DU_max  (4 features)
```

### 📈 Contoh Perhitungan

#### Data: H_vector
```python
H_vector = [0.120, 0.130, 0.110, 0.120, 0.140, 0.110, 0.120, 0.130]
```

#### Perhitungan:

**1. H_mean (Rata-rata)**
```python
H_mean = (0.120 + 0.130 + 0.110 + 0.120 + 0.140 + 0.110 + 0.120 + 0.130) / 8
H_mean = 0.9800 / 8
H_mean = 0.1225 detik (122.5ms)
```

**Interpretasi:**
- User rata-rata menahan tombol selama **122.5ms**
- Ini adalah **baseline hold time** user ini

---

**2. H_std (Standar Deviasi)**
```python
# Step 1: Hitung deviasi dari mean
deviations = [
    (0.120 - 0.1225)² = 0.00000625,
    (0.130 - 0.1225)² = 0.00005625,
    (0.110 - 0.1225)² = 0.00015625,
    ... (dst)
]

# Step 2: Rata-rata deviasi
variance = sum(deviations) / 8 = 0.000109375

# Step 3: Akar kuadrat
H_std = √0.000109375 = 0.0105 detik (10.5ms)
```

**Interpretasi:**
- Deviasi standar **10.5ms** = Sangat konsisten!
- **H_std < 20ms** = User mengetik dengan hold time yang stabil
- **H_std > 50ms** = User mengetik dengan hold time yang tidak teratur

---

**3. H_min (Minimum)**
```python
H_min = min([0.120, 0.130, 0.110, 0.120, 0.140, 0.110, 0.120, 0.130])
H_min = 0.110 detik (110ms)
```

**Interpretasi:**
- Hold time **tercepat** adalah **110ms**
- Ini menunjukkan **kecepatan maksimal** user saat menekan tombol

---

**4. H_max (Maximum)**
```python
H_max = max([0.120, 0.130, 0.110, 0.120, 0.140, 0.110, 0.120, 0.130])
H_max = 0.140 detik (140ms)
```

**Interpretasi:**
- Hold time **terlama** adalah **140ms**
- Range (max - min) = 140 - 110 = **30ms**
- Range kecil = Konsisten!

---

### 🎯 Keuntungan Statistical Features

**1. Fixed Size (Ukuran Tetap)**
```python
# Tanpa statistical features:
Password "pass" (4 char) → H_vector = [4 nilai]
Password "password" (8 char) → H_vector = [8 nilai]
# Ukuran berbeda = Susah untuk ML!

# Dengan statistical features:
Password "pass" → H_mean, H_std, H_min, H_max = [4 nilai]
Password "password" → H_mean, H_std, H_min, H_max = [4 nilai]
# Ukuran sama = Mudah untuk ML!
```

**2. Menangkap Karakteristik Umum**
```python
# Statistical features menangkap:
- Kecepatan rata-rata (mean)
- Konsistensi (std dev)
- Range kemampuan (min/max)

# Cocok untuk algoritma seperti:
- Random Forest
- Support Vector Machine
- Logistic Regression
```

**3. Tahan Terhadap Outliers (dengan kombinasi Mean + Median)**
```python
# Jika ada typo atau pause lama:
H_vector = [0.12, 0.13, 2.50, 0.11, 0.12]  # Ada outlier 2.50
H_mean = 0.596  # Terpengaruh outlier
H_median = 0.12  # Tidak terpengaruh outlier
```

---

### 📊 Contoh Lengkap Semua Statistical Features

Password: `password` (8 karakter)

#### H (Hold Time)
```python
H_vector = [0.120, 0.130, 0.110, 0.120, 0.140, 0.110, 0.120, 0.130]

H_mean = 0.1225  # Rata-rata hold 122.5ms
H_std  = 0.0105  # Deviasi 10.5ms (sangat konsisten!)
H_min  = 0.110   # Tercepat 110ms
H_max  = 0.140   # Terlambat 140ms
```

#### DD (Down-Down)
```python
DD_vector = [0.250, 0.240, 0.260, 0.250, 0.245, 0.255, 0.250]

DD_mean = 0.2500  # Rata-rata interval 250ms
DD_std  = 0.0065  # Deviasi 6.5ms (rhythm sangat stabil!)
DD_min  = 0.240   # Tercepat 240ms
DD_max  = 0.260   # Terlambat 260ms
```

#### UD (Up-Down)
```python
UD_vector = [0.130, 0.110, 0.150, 0.130, 0.105, 0.145, 0.130]

UD_mean = 0.1286  # Rata-rata jeda 128.6ms
UD_std  = 0.0175  # Deviasi 17.5ms
UD_min  = 0.105   # Jeda terpendek 105ms
UD_max  = 0.150   # Jeda terpanjang 150ms
```

#### UU (Up-Up)
```python
UU_vector = [0.260, 0.240, 0.270, 0.260, 0.245, 0.265, 0.260]

UU_mean = 0.2571
UU_std  = 0.0107
UU_min  = 0.240
UU_max  = 0.270
```

#### DU (Down-Up)
```python
DU_vector = [0.380, 0.370, 0.390, 0.380, 0.375, 0.385, 0.380]

DU_mean = 0.3800
DU_std  = 0.0065
DU_min  = 0.370
DU_max  = 0.390
```

---

## 4. Advanced Features (Fitur Lanjutan) 🆕 FITUR BARU

### 📝 Definisi

Advanced features adalah **fitur turunan** yang dihitung dari raw vectors dan statistical features. Fitur ini menggambarkan **pola perilaku** user secara keseluruhan.

> 🚀 **Catatan:** Semua fitur di section ini **DITAMBAHKAN BARU** untuk behavioral analysis dan user profiling. Original code tidak memiliki fitur-fitur ini.

### 🎯 8 Advanced Features

---

### 4.1 Rollover Frequency

**Definisi:** Jumlah kali terjadi **key overlap** (UD < 0).

**Rumus:**
```python
rollover_frequency = count(UD[i] < 0 for all i)
```

**Contoh:**
```python
UD_vector = [0.130, -0.020, 0.150, -0.015, 0.105, 0.145, -0.010]
#                    ↑ overlap   ↑ overlap           ↑ overlap

rollover_frequency = 3  # Ada 3 key overlap
```

**Interpretasi:**
| Nilai | Interpretasi | Typing Style |
|-------|--------------|--------------|
| 0 | Tidak ada overlap | Hunt-and-peck (ketik satu-satu) |
| 1-3 | Beberapa overlap | Semi touch typing |
| 4+ | Banyak overlap | Full touch typing (cepat) |

**Biometric Significance:**
- Rollover adalah **ciri khas unik** dari cara mengetik seseorang
- Touch typist vs hunt-and-peck typist sangat berbeda!

---

### 4.2 Error Rate

**Definisi:** Rasio jumlah backspace terhadap total karakter.

**Rumus:**
```python
error_rate = backspace_count / total_keys
```

**Contoh:**
```python
# User ketik: "passwrod" → backspace → "password"
backspace_count = 1
total_keys = 9  # 8 karakter + 1 backspace

error_rate = 1 / 9 = 0.111 (11.1%)
```

**Interpretasi:**
| Error Rate | Interpretasi |
|------------|--------------|
| 0% | Perfect typing (tidak ada typo) |
| < 5% | Sangat baik (occasional typo) |
| 5-15% | Normal (beberapa typo) |
| > 15% | Banyak typo (cognitive load tinggi) |

**Biometric Significance:**
- Error rate menggambarkan **cognitive load** dan **familiarity** dengan password
- User yang sering login punya error rate lebih rendah

---

### 4.3 Typing Speed

**Definisi:** Kecepatan mengetik dalam karakter per detik.

**Rumus:**
```python
typing_speed = total_keys / total_duration
```

**Contoh:**
```python
# Password: "password" (8 karakter)
total_duration = 2.0 detik

typing_speed = 8 / 2.0 = 4.0 chars/sec
```

**Konversi ke CPM (Characters Per Minute):**
```python
CPM = typing_speed × 60
CPM = 4.0 × 60 = 240 CPM

# WPM (Words Per Minute) ≈ CPM / 5
WPM = 240 / 5 = 48 WPM
```

**Interpretasi:**
| Typing Speed | CPM | WPM | Level |
|--------------|-----|-----|-------|
| < 2 chars/sec | < 120 | < 24 | Slow (hunt-and-peck) |
| 2-4 chars/sec | 120-240 | 24-48 | Average |
| 4-6 chars/sec | 240-360 | 48-72 | Fast |
| > 6 chars/sec | > 360 | > 72 | Very fast (touch typing) |

**Biometric Significance:**
- Typing speed adalah **baseline proficiency** user
- Konsisten antar session = Ciri khas biometrik

---

### 4.4 Coefficient of Variation (CV)

**Definisi:** Rasio standar deviasi terhadap mean (normalized consistency metric).

**Rumus:**
```python
CV = (std_dev / mean) × 100%
```

**Kenapa CV Lebih Baik dari Std Dev?**
```python
# User A (slow typist):
H_mean = 0.200, H_std = 0.020
H_cv = 0.020 / 0.200 = 0.10 (10% variasi)

# User B (fast typist):
H_mean = 0.100, H_std = 0.020
H_cv = 0.020 / 0.100 = 0.20 (20% variasi)

# Std dev sama (0.020), tapi CV berbeda!
# CV menunjukkan User A lebih konsisten secara relatif!
```

---

#### 4.4.1 H_cv (Hold Time Consistency)
```python
H_mean = 0.1225
H_std = 0.0105

H_cv = 0.0105 / 0.1225 = 0.0857 (8.57%)
```

**Interpretasi:**
| H_cv | Interpretasi |
|------|--------------|
| < 10% | Sangat konsisten (professional typist) |
| 10-20% | Konsisten (normal user) |
| 20-30% | Agak variatif (occasional inconsistency) |
| > 30% | Sangat variatif (erratic typing) |

---

#### 4.4.2 DD_cv (Rhythm Consistency)
```python
DD_mean = 0.2500
DD_std = 0.0065

DD_cv = 0.0065 / 0.2500 = 0.026 (2.6%)
```

**Interpretasi:**
- DD_cv = 2.6% → **Rhythm sangat stabil!**
- Ini menunjukkan user punya **internal metronome** yang baik
- Ciri khas dari muscle memory yang kuat

---

#### 4.4.3 UD_cv (Pause Consistency)
```python
UD_mean = 0.1286
UD_std = 0.0175

UD_cv = 0.0175 / 0.1286 = 0.136 (13.6%)
```

**Interpretasi:**
- UD_cv biasanya **lebih tinggi** dari DD_cv karena dipengaruhi rollover
- UD_cv > 100% = Ada rollover yang signifikan (nilai negatif)

---

#### 4.4.4 UU_cv (Overall Cycle Consistency)
```python
UU_mean = 0.2571
UU_std = 0.0107

UU_cv = 0.0107 / 0.2571 = 0.0416 (4.16%)
```

**Interpretasi:**
- UU_cv menggambarkan konsistensi **keseluruhan cycle**
- Mirip dengan DD_cv tapi memperhitungkan hold time variation

---

#### 4.4.5 DU_cv (Full Span Consistency)
```python
DU_mean = 0.3800
DU_std = 0.0065

DU_cv = 0.0065 / 0.3800 = 0.0171 (1.71%)
```

**Interpretasi:**
- DU_cv paling rendah karena mengukur **span penuh**
- Variation dari H dan DD saling cancel out

---

### 🎯 Contoh Lengkap Advanced Features

Password: `password` (8 karakter, 2 detik total)

```python
{
  "rollover_frequency": 3,     # 3 key overlaps
  "error_rate": 0.0,           # No typo (perfect)
  "typing_speed": 4.0,         # 4 chars/sec (240 CPM / 48 WPM)
  "H_cv": 0.0857,              # 8.57% variasi hold time
  "DD_cv": 0.026,              # 2.6% variasi rhythm (sangat stabil!)
  "UD_cv": 0.136,              # 13.6% variasi pause
  "UU_cv": 0.0416,             # 4.16% variasi cycle
  "DU_cv": 0.0171              # 1.71% variasi span
}
```

---

## 5. Quality Metrics (Metrik Kualitas) 🆕 FITUR BARU

### 📝 Definisi

Quality metrics adalah **penilaian otomatis** terhadap kualitas sample yang dikumpulkan. Sistem memberikan **warning non-blocking** jika ada anomali.

> 🚀 **Catatan:** Sistem quality assessment ini **DITAMBAHKAN BARU** untuk memastikan kualitas dataset. Original code tidak memiliki validasi kualitas otomatis.

### 🎯 3 Quality Metrics

---

### 5.1 Quality Label

**Definisi:** Klasifikasi kualitas sample berdasarkan score.

**3 Level:**
| Label | Score | Interpretasi |
|-------|-------|--------------|
| `good` | 80-100 | Sample berkualitas tinggi, konsisten |
| `questionable` | 60-79 | Sample dengan beberapa irregularity |
| `poor` | 0-59 | Sample dengan banyak masalah |

---

### 5.2 Quality Score

**Definisi:** Skor numerik (0-100) berdasarkan **penalty system**.

**Base Score:** 100 poin

**Penalty Rules:**

#### 1. Long Holds (Hold Time > 1 detik)
```python
long_holds = count(H[i] > 1.0 for all i)
if long_holds > 0:
    score -= 20
    warning = f"Very long hold times detected: {long_holds} keys held > 1s"
```

**Contoh:**
```python
H_vector = [0.12, 0.13, 2.50, 0.11, 0.12]  # Ada 2.50 detik (macet?)
# Penalty: -20 poin
# Warning: "Very long hold times detected: 1 keys held > 1s"
```

---

#### 2. Long Pauses (DD > 2 detik)
```python
long_pauses = count(DD[i] > 2.0 for all i)
if long_pauses > 0:
    score -= 15
    warning = f"Long pauses detected: {long_pauses} intervals > 2s"
```

**Contoh:**
```python
DD_vector = [0.25, 0.24, 3.50, 0.26, 0.25]  # Ada pause 3.5 detik
# Penalty: -15 poin
# Warning: "Long pauses detected: 1 intervals > 2s"
```

**Penyebab:**
- User teralihkan (baca password, lupa password, dll)
- Tidak fokus

---

#### 3. Super Fast Typing (DD < 0.05 detik / 50ms)
```python
super_fast = count(DD[i] < 0.05 for all i)
if super_fast > len(DD) * 0.3:  # > 30% super fast
    score -= 10
    warning = f"Unusually fast typing: {super_fast} intervals < 50ms"
```

**Contoh:**
```python
DD_vector = [0.03, 0.04, 0.03, 0.25, 0.26]  # 3 dari 5 = 60% super fast
# Penalty: -10 poin
# Warning: "Unusually fast typing: 3 intervals < 50ms"
```

**Penyebab:**
- Spam keyboard (mashing keys)
- Copy-paste (automated input)

---

#### 4. High Variance (CV > 150%)
```python
if DD_cv > 1.5:  # CV > 150%
    score -= 10
    warning = "High timing variance detected (inconsistent rhythm)"
```

**Contoh:**
```python
DD_vector = [0.10, 0.80, 0.15, 0.70, 0.12]  # Sangat tidak konsisten
DD_mean = 0.374, DD_std = 0.335
DD_cv = 0.335 / 0.374 = 0.896 (89.6%)
# Tidak kena penalty (< 150%)

DD_vector = [0.05, 2.50, 0.10, 3.00, 0.08]  # Ekstrem tidak konsisten
DD_mean = 1.146, DD_std = 1.425
DD_cv = 1.425 / 1.146 = 1.243 (124.3%)
# Masih belum penalty

DD_vector = [0.05, 5.00, 0.10, 6.00, 0.08]  # Super tidak konsisten
DD_mean = 2.246, DD_std = 2.862
DD_cv = 2.862 / 2.246 = 1.274 (127.4%)
# Hampir penalty (threshold 150%)
```

**Penyebab:**
- User ragu-ragu (lupa password)
- Teralihkan berkali-kali
- Tidak fokus

---

#### 5. Excessive Rollovers (> 80%)
```python
rollover_ratio = rollover_count / total_transitions
if rollover_ratio > 0.8:
    score -= 5
    warning = f"Very high rollover rate: {rollover_ratio*100:.0f}%"
```

**Contoh:**
```python
UD_vector = [-0.02, -0.01, -0.03, -0.02, 0.10]  # 4 dari 5 = 80%
rollover_ratio = 4 / 5 = 0.8 (80%)
# Penalty: -5 poin
# Warning: "Very high rollover rate: 80%"
```

**Catatan:**
- Rollover tinggi **bukan masalah** untuk touch typist
- Tapi rollover **terlalu tinggi** (> 80%) bisa jadi spam

---

### 5.3 Quality Warnings

**Definisi:** Array JSON berisi **daftar warning** yang terdeteksi.

**Format:**
```json
{
  "quality_warnings": [
    "Long pauses detected: 2 intervals > 2s",
    "High timing variance detected (inconsistent rhythm)"
  ]
}
```

---

### 📊 Contoh Kasus Quality Assessment

#### Kasus 1: Sample Berkualitas Tinggi ✅
```python
# Data:
H_vector = [0.12, 0.13, 0.11, 0.12, 0.14, 0.11, 0.12, 0.13]
DD_vector = [0.25, 0.24, 0.26, 0.25, 0.24, 0.26, 0.25]
UD_vector = [0.13, 0.11, 0.15, 0.13, 0.10, 0.16, 0.13]

# Assessment:
long_holds = 0      # Tidak ada hold > 1s
long_pauses = 0     # Tidak ada pause > 2s
super_fast = 0      # Tidak ada interval < 50ms
DD_cv = 0.026       # 2.6% (sangat konsisten!)
rollover_ratio = 0  # Tidak ada rollover

# Result:
{
  "quality_label": "good",
  "quality_score": 100,
  "quality_warnings": []
}
```

---

#### Kasus 2: Sample dengan Pause ⚠️
```python
# Data:
H_vector = [0.12, 0.13, 0.11, 0.12, 0.14]
DD_vector = [0.25, 3.50, 0.26, 0.25]  # Ada pause 3.5s!
UD_vector = [0.13, 3.39, 0.15, 0.13]

# Assessment:
long_holds = 0      # OK
long_pauses = 1     # ❌ Ada pause 3.5s → Penalty -15
super_fast = 0      # OK
DD_cv = 0.850       # 85% (agak tinggi tapi < 150%)
rollover_ratio = 0  # OK

# Result:
{
  "quality_label": "good",
  "quality_score": 85,  # 100 - 15 = 85
  "quality_warnings": [
    "Long pauses detected: 1 intervals > 2s"
  ]
}
```

---

#### Kasus 3: Sample dengan Banyak Masalah ❌
```python
# Data:
H_vector = [0.12, 2.50, 0.11, 0.12]  # Ada hold 2.5s!
DD_vector = [0.03, 0.04, 3.00]       # Super fast + long pause!
UD_vector = [-0.02, 0.10, 2.89]

# Assessment:
long_holds = 1      # ❌ Ada hold 2.5s → Penalty -20
long_pauses = 1     # ❌ Ada pause 3.0s → Penalty -15
super_fast = 2      # ❌ 2 dari 3 = 67% > 30% → Penalty -10
DD_cv = 1.856       # ❌ 185.6% > 150% → Penalty -10
rollover_ratio = 0.33  # OK (< 80%)

# Result:
{
  "quality_label": "poor",
  "quality_score": 45,  # 100 - 20 - 15 - 10 - 10 = 45
  "quality_warnings": [
    "Very long hold times detected: 1 keys held > 1s",
    "Long pauses detected: 1 intervals > 2s",
    "Unusually fast typing: 2 intervals < 50ms",
    "High timing variance detected (inconsistent rhythm)"
  ]
}
```

---

### 🎯 Menggunakan Quality Metrics

#### Saat Collection (Real-time Feedback)
```javascript
// Frontend menampilkan:
if (quality_label === 'good') {
  showMessage('✅ Sample berkualitas tinggi! (Score: 100/100)');
} else if (quality_label === 'questionable') {
  showMessage('⚠️ Sample OK tapi ada irregularity (Score: 70/100)');
  showWarnings(quality_warnings);
} else {
  showMessage('❌ Sample kurang baik (Score: 45/100)');
  showWarnings(quality_warnings);
}
```

#### Post-Collection (Data Filtering)
```python
# Filter dataset sebelum training:
df_filtered = df[df['quality_label'] == 'good']
# Atau:
df_filtered = df[df['quality_score'] >= 80]
```

---

## 6. Contoh Data Lengkap

### 📄 Sample Lengkap dalam CSV

```csv
username,timestamp,password_hash,data_type,total_duration,backspace_count,typing_rollover_ratio,H_vector,DD_vector,UD_vector,UU_vector,DU_vector,H_features,DD_features,UD_features,UU_features,DU_features,H_mean,H_std,H_min,H_max,DD_mean,DD_std,DD_min,DD_max,UD_mean,UD_std,UD_min,UD_max,UU_mean,UU_std,UU_min,UU_max,DU_mean,DU_std,DU_min,DU_max,rollover_frequency,error_rate,typing_speed,H_cv,DD_cv,UD_cv,UU_cv,DU_cv,quality_label,quality_score,quality_warnings
testuser,2025-12-17 14:30:00,5e884...,enrollment,2.0,0,0.0,"[0.12,0.13,0.11,0.12,0.14,0.11,0.12,0.13]","[0.25,0.24,0.26,0.25,0.24,0.26,0.25]","[0.13,0.11,0.15,0.13,0.10,0.16,0.13]","[0.26,0.24,0.27,0.26,0.24,0.27,0.26]","[0.38,0.37,0.39,0.38,0.37,0.39,0.38]","{""H.p_0"":0.12,...}","{""DD.p_0.a_1"":0.25,...}","{""UD.p_0.a_1"":0.13,...}","{""UU.p_0.a_1"":0.26,...}","{""DU.p_0.a_1"":0.38,...}",0.1225,0.0105,0.11,0.14,0.2500,0.0065,0.24,0.26,0.1286,0.0175,0.10,0.16,0.2571,0.0107,0.24,0.27,0.3800,0.0065,0.37,0.39,0,0.0,4.0,0.0857,0.026,0.136,0.0416,0.0171,good,100,"[]"
```

### 📊 Sample dalam JSON (Lebih Readable)

```json
{
  "username": "testuser",
  "timestamp": "2025-12-17 14:30:00",
  "password_hash": "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8",
  "data_type": "enrollment",
  
  "global_features": {
    "total_duration": 2.0,
    "backspace_count": 0,
    "typing_rollover_ratio": 0.0
  },
  
  "raw_vectors": {
    "H_vector": [0.12, 0.13, 0.11, 0.12, 0.14, 0.11, 0.12, 0.13],
    "DD_vector": [0.25, 0.24, 0.26, 0.25, 0.24, 0.26, 0.25],
    "UD_vector": [0.13, 0.11, 0.15, 0.13, 0.10, 0.16, 0.13],
    "UU_vector": [0.26, 0.24, 0.27, 0.26, 0.24, 0.27, 0.26],
    "DU_vector": [0.38, 0.37, 0.39, 0.38, 0.37, 0.39, 0.38]
  },
  
  "labeled_features": {
    "H_features": {
      "H.p_0": 0.12,
      "H.a_1": 0.13,
      "H.s_2": 0.11,
      "H.s_3": 0.12,
      "H.w_4": 0.14,
      "H.o_5": 0.11,
      "H.r_6": 0.12,
      "H.d_7": 0.13
    },
    "DD_features": {
      "DD.p_0.a_1": 0.25,
      "DD.a_1.s_2": 0.24,
      "DD.s_2.s_3": 0.26,
      "DD.s_3.w_4": 0.25,
      "DD.w_4.o_5": 0.24,
      "DD.o_5.r_6": 0.26,
      "DD.r_6.d_7": 0.25
    }
  },
  
  "statistical_features": {
    "H": { "mean": 0.1225, "std": 0.0105, "min": 0.11, "max": 0.14 },
    "DD": { "mean": 0.2500, "std": 0.0065, "min": 0.24, "max": 0.26 },
    "UD": { "mean": 0.1286, "std": 0.0175, "min": 0.10, "max": 0.16 },
    "UU": { "mean": 0.2571, "std": 0.0107, "min": 0.24, "max": 0.27 },
    "DU": { "mean": 0.3800, "std": 0.0065, "min": 0.37, "max": 0.39 }
  },
  
  "advanced_features": {
    "rollover_frequency": 0,
    "error_rate": 0.0,
    "typing_speed": 4.0,
    "H_cv": 0.0857,
    "DD_cv": 0.026,
    "UD_cv": 0.136,
    "UU_cv": 0.0416,
    "DU_cv": 0.0171
  },
  
  "quality_metrics": {
    "quality_label": "good",
    "quality_score": 100,
    "quality_warnings": []
  }
}
```

---

## 🎓 Rangkuman

### 📊 Total Features per Sample

| Kategori | Jumlah | Status | Deskripsi |
|----------|--------|--------|-----------|
| **Labeled Features** | ~50 | 🆕 **BARU** | Raw vectors dengan label karakter + posisi |
| **Statistical Features** | 20 | 🆕 **BARU** | Mean, Std, Min, Max untuk 5 vektor |
| **Advanced Features** | 8 | 🆕 **BARU** | Rollover freq, error rate, typing speed, CV |
| **Quality Metrics** | 3 | 🆕 **BARU** | Label, score, warnings (quality assessment) |
| **Metadata** | 8 | ✅ **ORIGINAL** | Username, timestamp, hash, dll |
| **TOTAL** | ~139 | **5 Original + 134 Baru** | Dataset sangat komprehensif! |

---

### 🎯 Kegunaan per Kategori

| Kategori | Kegunaan Utama |
|----------|----------------|
| **Raw Vectors** | Neural networks, deep learning (sequence data) |
| **Labeled Features** | Position-aware ML, character-specific patterns |
| **Statistical Features** | Random Forest, SVM, Logistic Regression |
| **Advanced Features** | Behavioral analysis, user profiling |
| **Quality Metrics** | Data filtering, anomaly detection |

---

### 🚀 Best Practices

1. **Collection Phase:**
   - Gunakan quality metrics untuk real-time feedback
   - Filter out samples dengan `quality_label = 'poor'`

2. **Feature Selection:**
   - Start dengan statistical + advanced features (28 features)
   - Tambahkan raw vectors jika perlu (untuk deep learning)
   - Labeled features untuk special cases (character-specific patterns)

3. **Normalization:**
   - Z-score normalization per-user untuk statistical features
   - Min-max scaling untuk advanced features

4. **Model Training:**
   - Random Forest: Statistical + Advanced features
   - SVM: Statistical + Advanced features (dengan kernel)
   - Neural Network: Raw vectors (sequence) + Statistical features

---

## 📚 Referensi

1. **Monrose, F., & Rubin, A. D. (2000)**. "Keystroke dynamics as a biometric for authentication." *Future Generation Computer Systems*, 16(4), 351-359.

2. **Killourhy, K. S., & Maxion, R. A. (2009)**. "Comparing anomaly-detection algorithms for keystroke dynamics." *DSN*, 9, 125-134.

3. **Teh, P. S., Teoh, A. B. J., & Yue, S. (2013)**. "A survey of keystroke dynamics biometrics." *The Scientific World Journal*, 2013.

4. **Zhong, Y., Deng, Y., & Jain, A. K. (2012)**. "Keystroke dynamics for user authentication." *CVPRW*, 117-123.

---

**Dokumen ini dibuat untuk:** Keystroke Dynamics Dataset Collection System  
**Versi:** 2.0 (Hybrid Mode - Solusi C)  
**Tanggal:** 17 Desember 2025
