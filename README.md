# Keystrokes-Dynamic

Berdasarkan analisis kode sumber (source code) yang Anda unggah, berikut adalah draf **README.md** yang komprehensif dan profesional untuk proyek ini. Dokumen ini mencakup deskripsi proyek, cara instalasi, struktur file, dan penjelasan teknis mengenai algoritma biometrik yang digunakan.

-----

# Keystroke Dynamics Authentication System

Sistem autentikasi biometrik berbasis web yang memverifikasi identitas pengguna tidak hanya berdasarkan **apa** yang mereka ketik (kata sandi), tetapi juga **bagaimana** mereka mengetiknya (pola ritme, kecepatan, dan durasi tekanan tombol).

Proyek ini dibangun menggunakan Python (Flask) untuk backend dan Vanilla JavaScript untuk pengambilan data keystroke di frontend.

## 📋 Fitur Utama

1.  **Pendaftaran Biometrik (Enrollment):**
      * Mengambil sampel pola ketikan pengguna (minimal 2 sampel awal).
      * Menghitung fitur statistik dari pola ketikan untuk membuat profil pengguna.
2.  **Verifikasi Login (Authentication):**
      * Membandingkan pola ketikan saat login dengan profil yang tersimpan di database.
      * Menggunakan algoritma jarak vektor (Manhattan/Euclidean distance yang dimodifikasi) untuk menentukan skor kemiripan.
3.  **Analisis Vektor Keystroke:**
      * **H-Vector (Hold Time):** Durasi tombol ditekan.
      * **Flight Times (Latency):**
          * **DD (Down-Down):** Waktu antara penekanan tombol pertama dan kedua.
          * **UD (Up-Down):** Waktu antara pelepasan tombol pertama dan penekanan tombol kedua.
          * **UU (Up-Up)** & **DU (Down-Up)**.
4.  **Hybrid Storage:**
      * Menyimpan data di **SQLite** (`user_vectors`) untuk operasional aplikasi.
      * Mencatat log ke **CSV** (`biometric_auth.csv`) untuk keperluan analisis data/dataset.
5.  **Deteksi Anomali Sederhana:**
      * Mendeteksi *Shift Dominance* (Kiri/Kanan).
      * Mendeteksi *Rollover Ratio* (pengetikan yang tumpang tindih).

## 🛠️ Teknologi yang Digunakan

  * **Backend:** Python 3, Flask, Numpy.
  * **Database:** SQLite3.
  * **Frontend:** HTML5, CSS3, JavaScript (Native).
  * **Library Tambahan:** `flask-cors` (untuk menangani Cross-Origin Resource Sharing).

## 📂 Struktur Proyek

```text
Keystrokes/
├── biometric_auth.db       # Database utama (SQLite)
├── biometric_auth.csv      # Log data (CSV)
├── README.md               # Dokumentasi ini
└── webV2/                  # Folder Aplikasi Utama
    ├── app.py              # Entry point (Flask Server & Routing)
    ├── db.py               # Modul manajemen Database (SQLite & CSV)
    ├── verifier.py         # Modul algoritma verifikasi biometrik (The "Brain")
    └── templates/          # Halaman antarmuka pengguna
        ├── home.html       # Landing page
        ├── login.html      # Halaman Login
        └── register.html   # Halaman Pendaftaran
```

## 🚀 Cara Instalasi dan Menjalankan

### Prasyarat

Pastikan Python 3 sudah terinstal di komputer Anda.

### 1\. Instalasi Dependencies

Buka terminal atau command prompt, lalu instal library Python yang dibutuhkan:

```bash
pip install flask flask-cors numpy
```

### 2\. Menjalankan Aplikasi

Navigasikan terminal ke folder `webV2` dan jalankan `app.py`:

```bash
cd Keystrokes/webV2
python app.py
```

### 3\. Akses Aplikasi

Buka browser dan kunjungi alamat berikut:
`http://127.0.0.1:5000/`

## 📖 Cara Penggunaan

1.  **Daftar (Register):**
      * Masuk ke menu "Daftar Baru".
      * Masukkan Username dan Password utama.
      * Ketik ulang password tersebut sebanyak minimal 2 kali pada kolom yang disediakan untuk melatih sistem mengenali pola Anda.
2.  **Login:**
      * Masuk ke menu "Masuk (Login)".
      * Masukkan Username dan ketik Password Anda secara natural.
      * Sistem akan menghitung skor. Jika skor di bawah **Threshold (0.45)**, login diterima. Jika gaya mengetik berbeda (meskipun password benar), login akan ditolak.

## 🧠 Penjelasan Teknis (Algoritma)

Sistem bekerja dengan menangkap *timestamp* `keydown` dan `keyup` di browser, kemudian mengirimkannya ke server.

### Ekstraksi Fitur (`process_web_events` di `app.py`)

Data mentah diubah menjadi vektor fitur:

1.  `Hold Time`: $t_{up} - t_{down}$
2.  `Flight Time`: Selisih waktu antara tombol berurutan ($Key_1$ dan $Key_2$).
3.  `Rollover`: Persentase penekanan tombol yang tumpang tindih (menekan tombol berikutnya sebelum melepas tombol sebelumnya).

### Verifikasi (`Verifier` di `verifier.py`)

1.  **Pembersihan Data:** Sistem mencari "panjang vektor dominan" dari data latihan untuk membuang sampel yang rusak/salah ketik.
2.  **Profil Referensi:** Menghitung rata-rata (mean) dari vektor fitur yang bersih.
3.  **Perhitungan Jarak:** Menggunakan selisih absolut antara vektor input login dan profil referensi. Nilai selisih dibatasi (*capped*) untuk menghindari *outlier* ekstrem.
4.  **Scoring:** Skor akhir adalah kombinasi berbobot dari kemiripan vektor (70%) dan fitur makro seperti durasi total & ritme (30%).
      * **Threshold:** `< 0.45` (Lolos)
      * **Threshold:** `> 0.45` (Ditolak/Curiga)

## ⚠️ Catatan Pengembang (Dev Mode)

  * **Penyimpanan Password:**
    Saat ini, file `db.py` memiliki fitur `save_dev_credentials` yang menyimpan password asli dalam bentuk *plain text* di tabel `users` untuk tujuan debugging/pengembangan.

    > **PENTING:** Hapus atau nonaktifkan fungsi ini sebelum digunakan di lingkungan produksi (production) demi keamanan.

  * **Threshold Tuning:**
    Sensitivitas sistem dapat diatur dengan mengubah variabel `REAL_THRESHOLD` atau `self.THRESHOLD` di dalam file `webV2/verifier.py`.

-----

*Dibuat berdasarkan analisis source code proyek Keystrokes-Dynamic.*
