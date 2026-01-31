# Keystrokes-Dynamic

Berdasarkan analisis kode sumber (source code) yang Anda unggah, berikut adalah draf **README.md** yang komprehensif dan profesional untuk proyek ini. Dokumen ini mencakup deskripsi proyek, cara instalasi, struktur file, dan penjelasan teknis mengenai algoritma biometrik yang digunakan.

-----

# Keystroke Dynamics Authentication System

Sistem autentikasi biometrik berbasis web yang memverifikasi identitas pengguna tidak hanya berdasarkan **apa** yang mereka ketik (kata sandi), tetapi juga **bagaimana** mereka mengetiknya (pola ritme, kecepatan, dan durasi tekanan tombol).

Proyek ini dibangun menggunakan Python (Flask) untuk backend dan Vanilla JavaScript untuk pengambilan data keystroke di frontend.

## 📋 Fitur Utama

1.  **Pendaftaran Biometrik (Enrollment):**
      * Mengambil sampel pola ketikan pengguna (minimal 2 sampel).
      * Menghitung fitur statistik dari pola ketikan untuk membuat profil pengguna.
      * Character limiting: UI hanya menampilkan 1 karakter meskipun tombol ditahan lama.

2.  **Verifikasi Login (Authentication):**
      * Membandingkan pola ketikan saat login dengan profil yang tersimpan di database.
      * Hard rejection untuk anomaly ekstrem (perbedaan >0.5 detik).
      * Threshold ketat (0.30) untuk keamanan maksimal.

3.  **Dual Format Feature Extraction:**
      * **Legacy Vectors** (Backward Compatibility):
          * `H_vector`, `DD_vector`, `UD_vector`, `UU_vector`, `DU_vector`
      * **Character-Labeled Features** (Format Baru):
          * `H_features`: `{"H.a_0": 0.123, "H.b_1": 0.234, ...}`
          * `DD_features`: `{"DD.a_0.b_1": 0.145, ...}`
          * `UD_features`: `{"UD.a_0.b_1": 0.089, ...}`

4.  **Analisis Vektor Keystroke:**
      * **H (Hold Time):** Durasi tombol ditekan (dari keydown pertama sampai keyup).
      * **DD (Down-Down):** Waktu antara penekanan tombol pertama dan kedua.
      * **UD (Up-Down):** Waktu antara pelepasan tombol pertama dan penekanan tombol kedua.
      * **UU (Up-Up)** & **DU (Down-Up)**.

5.  **Hybrid Storage:**
      * Menyimpan data di **SQLite** (`user_vectors`) untuk operasional aplikasi.
      * Mencatat log ke **CSV** (`biometric_auth.csv`) untuk keperluan analisis data/dataset.
      * Auto schema migration: database otomatis menambah kolom baru.

6.  **Advanced Security Features:**
      * Modifier keys (Shift, Ctrl, Alt) tidak dihitung sebagai hold time - hanya penghubung.
      * Karakter khusus (!, @, #, dll) dibatasi di UI seperti huruf biasa.
      * Filter enrollment: hanya data `enrollment` yang digunakan untuk profil (bukan `login_attempt`).
      * Adaptive learning: login sukses ditambahkan ke profil enrollment.

7.  **Deteksi Anomali:**
      * Extreme anomaly detection: perbedaan >0.5 detik langsung ditolak.
      * Rollover ratio: deteksi pengetikan yang tumpang tindih.
      * Outlier capping: membatasi pengaruh nilai ekstrem.

## 🛠️ Teknologi yang Digunakan

  * **Backend:** Python 3.8+, Flask, Numpy
  * **Database:** SQLite3
  * **Frontend:** HTML5, CSS3, JavaScript (Vanilla - No Framework)
  * **Library Tambahan:** `flask-cors`

## 📂 Struktur Proyek

```text
Keystrokes-Dynamic/
├── biometric_auth.db       # Database utama (SQLite)
├── biometric_auth.csv      # Log data (CSV)
├── README.md               # Dokumentasi ini
├── venv/                   # Virtual environment (dibuat saat instalasi)
└── webV2/                  # Folder Aplikasi Utama
    ├── app.py              # Entry point (Flask Server & Feature Extraction)
    ├── db.py               # Modul manajemen Database (SQLite & CSV)
    ├── verifier.py         # Algoritma verifikasi biometrik
    ├── biometric_auth.db   # Database lokal
    ├── biometric_auth.csv  # Log data lokal
    ├── templates/          # Halaman antarmuka pengguna
    │   ├── home.html       # Landing page
    │   ├── login.html      # Halaman Login
    │   └── register.html   # Halaman Pendaftaran
    ├── test_verification.py        # Script analisis verifikasi
    ├── test_attack_simulation.py   # Script simulasi serangan
    ├── check_data_type.py          # Script cek data_type di DB
    └── analisis_visual.py          # Script visualisasi analisis
```

## 🚀 Cara Instalasi dan Menjalankan

### Prasyarat

Pastikan Python 3 sudah terinstal di komputer Anda. Untuk mengecek versi Python:

```bash
python --version
```

### 1\. Clone atau Download Repository

Clone repository ini atau download sebagai ZIP dan extract:

```bash
git clone https://github.com/Chaizaa/Keystrokes-Dynamic.git
cd Keystrokes-Dynamic
```

### 2\. Membuat Virtual Environment

**Untuk Windows (PowerShell/Command Prompt):**

```bash
python -m venv venv
```

**Untuk Linux/Mac:**

```bash
python3 -m venv venv
```

### 3\. Aktivasi Virtual Environment

**Untuk Windows (PowerShell):**

```powershell
.\venv\Scripts\Activate.ps1
```

**Untuk Windows (Command Prompt):**

```cmd
venv\Scripts\activate.bat
```

**Untuk Linux/Mac:**

```bash
source venv/bin/activate
```

> **Catatan:** Setelah aktivasi berhasil, Anda akan melihat `(venv)` di awal baris terminal Anda.

### 4\. Instalasi Dependencies

Dengan virtual environment yang sudah aktif, instal library Python yang dibutuhkan:

```bash
pip install flask flask-cors numpy
```

### 5\. Menjalankan Aplikasi

Navigasikan terminal ke folder `webV2` dan jalankan `app.py`:

```bash
cd webV2
python app.py
```

### 6\. Akses Aplikasi

Buka browser dan kunjungi alamat berikut:

```
http://127.0.0.1:5000/
```

### 7\. Menonaktifkan Virtual Environment

Setelah selesai menggunakan aplikasi, Anda dapat menonaktifkan virtual environment dengan perintah:

```bash
deactivate
```

## 📖 Cara Penggunaan

1.  **Daftar (Register):**
      * Masuk ke menu "Daftar Baru".
      * Masukkan Username dan Password utama.
      * Ketik ulang password tersebut sebanyak minimal 2 kali pada kolom yang disediakan.
      * **Tips:** Ketik dengan pola konsisten (kecepatan, ritme, hold time).
      * Jika menahan tombol lama (misalnya 2+ detik), UI hanya tampil 1 karakter tapi waktu tetap dicatat.

2.  **Login:**
      * Masuk ke menu "Masuk (Login)".
      * Masukkan Username dan ketik Password dengan pola yang sama seperti saat registrasi.
      * **Penting:** Jaga konsistensi pola ketikan!
          * Jika saat daftar menahan karakter tertentu lama, saat login juga harus sama.
          * Jika saat daftar cepat pindah antar karakter, saat login juga harus cepat.
      * Sistem akan menghitung skor. Jika skor di bawah **Threshold (0.30)**, login diterima.
      * Jika pola mengetik berbeda >0.5 detik (meskipun password benar), login akan **langsung ditolak**.

3.  **Karakter Khusus:**
      * Karakter dengan Shift (!, @, #, $, dll) juga dihitung timing-nya.
      * Shift, Ctrl, Alt tidak dihitung hold time (hanya penghubung).
      * Karakter khusus dibatasi di UI seperti huruf biasa.

## 🔬 Fitur Testing & Debugging

Sistem dilengkapi dengan script testing untuk analisis:

1.  **`test_verification.py`** - Analisis detail kenapa login gagal:
    ```bash
    python test_verification.py
    ```
    Output: Perbandingan profil vs login attempt dengan detail perbedaan per fitur.

2.  **`test_attack_simulation.py`** - Simulasi serangan (password benar, timing salah):
    ```bash
    python test_attack_simulation.py
    ```
    Output: Membuktikan sistem mendeteksi perbedaan timing meskipun password benar.

3.  **`check_data_type.py`** - Cek distribusi data enrollment vs login_attempt:
    ```bash
    python check_data_type.py
    ```

4.  **`analisis_visual.py`** - Visualisasi perbedaan pola ketikan:
    ```bash
    python analisis_visual.py
    ```

## 🧠 Penjelasan Teknis (Algoritma)

Sistem bekerja dengan menangkap *timestamp* `keydown` dan `keyup` di browser, kemudian mengirimkannya ke server.

### Frontend: Event Capture

**Register.html & Login.html:**
```javascript
// Event listener untuk keydown
typingInput.addEventListener('keydown', (event) => {
    const isModifier = ['Shift', 'Control', 'Alt', 'Meta', 'CapsLock']...
    
    // Batasi karakter di UI tapi catat waktu penuh
    if (event.repeat && !isModifier) {
        event.preventDefault();  // UI cuma tampil 1 karakter
        rawEvents.push({...isRepeat: true});  // Waktu tetap dicatat
    }
    
    // HANYA non-modifier yang direkam
    if (!isModifier) {
        rawEvents.push({key, code, evt: 'd', t: performance.now()});
    }
});
```

**Fitur Utama:**
- Modifier keys (Shift, Ctrl, Alt) **tidak dicatat** - hanya penghubung
- Karakter khusus (!, @, #) **dibatasi di UI** tapi timing **tetap dicatat penuh**
- Hold time dihitung dari **keydown pertama** sampai **keyup** (termasuk auto-repeat)

### Backend: Feature Extraction (`app.py`)

Data mentah dari browser diubah menjadi fitur biometrik:

**1. Parsing & Pairing:**
```python
# Hanya simpan waktu keydown PERTAMA (untuk hold time penuh)
if k_id not in temp_dict:
    temp_dict[k_id] = (waktu_down_pertama, karakter)

# Saat keyup, hitung hold time penuh
hold_time = waktu_up - temp_dict[k_id][0]
```

**2. Dual Format Features:**

**Legacy Vectors** (Backward compatibility):
- `H_vector = [0.123, 0.234, 0.345, ...]`
- `DD_vector`, `UD_vector`, `UU_vector`, `DU_vector`

**Character-Labeled Features** (Format baru - lebih presisi):
```python
H_features = {
    "H.t_0": 0.1734,    # Hold time 't' posisi 0
    "H.e_1": 0.1190,    # Hold time 'e' posisi 1
    "H.!_3": 3.4645,    # Hold time '!' posisi 3 (DITAHAN LAMA!)
    ...
}

DD_features = {
    "DD.t_0.e_1": 0.0968,     # Down-Down dari 't' ke 'e'
    "DD.!_3.2_4": 4.2622,     # Down-Down dari '!' ke '2'
    ...
}
```

**3. Macro Features:**
- `total_duration`: Durasi total ketik password
- `typing_rollover_ratio`: % ketikan yang overlap
- `char_sequence`: Array karakter asli `['t','e','s','!','2','3']`

### Verifikasi (`verifier.py`)

**Algoritma 5 Tahap:**

**1. Validasi Password Hash:**
```python
if input['password_hash'] != stored_hash:
    return {"result": False, "reason": "Password Salah"}
```

**2. Filter Sampel Bersih:**
```python
# Cari panjang vektor dominan (modus)
dominant_len = mode([len(s['H_vector']) for s in samples])

# Hanya ambil sampel konsisten
clean_samples = [s for s in samples if len(s['H_vector']) == dominant_len]
```

**3. Bangun Profil Rata-Rata:**
```python
# Profil untuk H_features (character-labeled)
h_profile = {
    'H.!_3': mean([3.4645, 4.1203, ...]),  # Rata-rata hold '!'
    ...
}
```

**4. Hitung Distance & Deteksi Anomaly:**
```python
for key in H_features:
    diff = abs(input[key] - profile[key])
    
    # HARD REJECTION untuk anomaly ekstrem
    if diff > 0.5:  # Beda >0.5 detik
        return {"result": False, "reason": "Pola waktu tidak cocok!"}
```

**5. Weighted Score:**
```python
# Bobot: 60% character-labeled features + 20% legacy + 20% macro
final_score = (w_vec * 0.2) + (w_features * 0.6) + (w_macro * 0.2)

# Threshold: <0.30 = LOLOS, >0.30 = DITOLAK
is_verified = final_score < 0.30
```

### Database Schema

**Tabel `user_vectors`:**
```sql
- username TEXT
- timestamp TEXT
- password_hash TEXT (SHA-256)
- char_sequence TEXT (JSON: ['t','e','s','!'])
- total_duration REAL
- typing_rollover_ratio REAL

-- Legacy vectors (JSON strings)
- H_vector TEXT
- DD_vector, UD_vector, UU_vector, DU_vector TEXT

-- New character-labeled features (JSON strings)  
- H_features TEXT     -- '{"H.t_0": 0.123, ...}'
- DD_features TEXT
- UD_features TEXT

-- Metadata
- data_type TEXT      -- 'enrollment' atau 'login_attempt'
- login_result TEXT   -- 'True'/'False' (jika login)
- login_score REAL
```

**Auto Schema Migration:**
Database otomatis menambah kolom baru tanpa manual ALTER TABLE.

### Security Features

**1. Extreme Anomaly Detection:**
- Perbedaan >0.5 detik pada 1 fitur = **langsung ditolak**
- Tidak perlu tunggu threshold scoring

**2. Adaptive Learning:**
- Login sukses → data ditambahkan ke enrollment
- Login gagal → disimpan sebagai `login_attempt` (tidak merusak profil)

**3. Outlier Capping:**
- Perbedaan maksimal yang dihitung = 1.0 detik
- Mencegah 1 outlier merusak skor keseluruhan

## ⚠️ Catatan Pengembang

  * **Dev Mode Password Storage:**
    File `db.py` memiliki fitur `save_dev_credentials` yang menyimpan password asli dalam bentuk *plain text* di tabel `users` untuk tujuan debugging.

    > **PENTING:** Hapus atau nonaktifkan fungsi ini sebelum produksi.

  * **Threshold Tuning:**
    Sensitivitas sistem dapat diatur dengan mengubah:
    - `THRESHOLD = 0.30` di `verifier.py` (skor maksimal untuk lolos)
    - `EXTREME_ANOMALY_THRESHOLD = 0.5` (deteksi perbedaan ekstrem)

  * **Bobot Features:**
    ```python
    final_score = (w_vec * 0.2) + (w_features * 0.6) + (w_macro * 0.2)
    # 60% character-labeled features
    # 20% legacy vectors
    # 20% macro (duration, rollover)
    ```

## 📊 Contoh Analisis

**Skenario:** User `tes` dengan password `tes!23`

**Enrollment:**
- Hold time '!': 3.46 detik (ditahan lama)
- Interval '!' → '2': 4.26 detik (lambat pindah)

**Login Attempt:**
- Hold time '!': 2.46 detik (lebih cepat)
- Interval '!' → '2': 2.51 detik (cepat pindah)

**Hasil:**
```
❌ LOGIN DITOLAK
Reason: Pola waktu tidak cocok!

Anomaly Detected:
- H.!_3: Diff 1.01 detik ⚠️ EXTREME!
- DD.!_3.2_4: Diff 1.76 detik ⚠️ EXTREME!
- UD.!_3.2_4: Diff 0.75 detik ⚠️ EXTREME!
```

**Kesimpulan:** Meskipun password **BENAR**, pola biometrik **BERBEDA** → **DITOLAK**

## 🎓 Pembelajaran dari Proyek

1. **Password Saja Tidak Cukup:**
   - Attacker bisa tahu password tapi pola ketikannya berbeda
   - Sistem biometrik menambah layer security

2. **Konsistensi adalah Kunci:**
   - User harus ketik dengan pola yang sama
   - Variasi kecil (0.1-0.2s) masih OK, tapi >0.5s ditolak

3. **Character-Labeled Features Lebih Presisi:**
   - `H.!_3` lebih informatif dari `H_vector[3]`
   - Memudahkan debugging dan analisis

4. **Adaptive Learning:**
   - Profil user berkembang dari waktu ke waktu
   - Login sukses memperbaiki akurasi profil

## 📚 Referensi

- Keystroke Dynamics: Biometric Authentication by Typing Patterns
- Manhattan Distance & Euclidean Distance untuk Vector Similarity
- Flask Framework Documentation
- Browser Performance API untuk High-Resolution Timestamps

---

**Dibuat oleh:** Chaizaa  
**Repository:** [Keystrokes-Dynamic](https://github.com/Chaizaa/Keystrokes-Dynamic)  
**Tanggal Update:** December 9, 2025  
**Status:** ✅ Production Ready (dengan catatan dev mode)
