# Quick Start Guide (Current Flow)

Panduan ini mengikuti alur aplikasi yang aktif saat ini:

- Registrasi dan enrollment dilakukan di halaman `/register`.
- Login biometrik dilakukan di halaman `/login`.
- Koleksi dataset riset publik dilakukan di halaman `/dataset`.

## 1. Jalankan Aplikasi

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Buka:
- Home: `http://127.0.0.1:5000/`
- Register: `http://127.0.0.1:5000/register`
- Login: `http://127.0.0.1:5000/login`
- Dataset capture: `http://127.0.0.1:5000/dataset`

## 2. Registrasi + Enrollment User

1. Masuk ke `/register`.
2. Isi username, email (opsional tapi direkomendasikan), dan password.
3. Lakukan verifikasi email jika diminta.
4. Ketik password yang sama berulang sampai target enrollment tercapai.

Catatan penting:
- Target enrollment UI saat ini: `100` sampel.
- Progress bersifat resumable (bisa dilanjutkan).
- Endpoint yang dipakai frontend: `POST /api/register_sample`.

Response sukses berisi progress:

```json
{
  "status": "success",
  "progress": {
    "current": 12,
    "target": 100,
    "complete": false
  }
}
```

## 3. Login Biometrik

1. Masuk ke `/login`.
2. Isi username atau email.
3. Ketik password secara natural (ritme seperti saat enrollment).
4. Submit untuk verifikasi.

Endpoint login aktif:
- `POST /api/login`

Kemungkinan hasil:
- `200` + `success: true` -> login berhasil.
- `200` + `requires_2fa: true` -> lanjut verifikasi 2FA.
- `403` + `reason: impostor_detected` -> ritme ketik tidak cocok.
- `429` + `reason: rate_limit_exceeded` -> terlalu banyak gagal login.

## 4. Dataset Collection (Riset)

Untuk kebutuhan dataset (terpisah dari login user biasa), gunakan `/dataset`.

Alur ringkas:
1. `POST /api/dataset/register` untuk membuat `subject_code` dan `session_token`.
2. `POST /api/dataset/submit` berulang dengan header `X-Session-Token`.
3. `GET /api/dataset/status/<subject_code>` untuk cek progres.

## 5. Format Event Keystroke

Backend sekarang membaca event format berikut:

```json
{
  "t": 1234.56,
  "evt": "d",
  "code": "KeyA",
  "key": "a"
}
```

Keterangan:
- `evt`: `d` untuk keydown, `u` untuk keyup.
- `t`: timestamp dari browser (umumnya `performance.now()`).

## 6. Troubleshooting Cepat

### User not registered
Penyebab: user belum punya sampel enrollment.
Solusi: selesaikan enrollment di `/register` terlebih dulu.

### Incorrect password / PASSWORD_MISMATCH
Penyebab: password yang diketik tidak sama dengan yang terdaftar.
Solusi: cek password utama, lalu ulangi.

### impostor_detected
Penyebab: pola ketikan berbeda signifikan.
Solusi: ketik dengan ritme yang konsisten seperti saat enrollment.

### rate_limit_exceeded
Penyebab: terlalu banyak percobaan gagal.
Solusi: tunggu sesuai kebijakan lockout lalu coba lagi.

## 7. Referensi Lanjutan

- API lengkap: `docs/API.md`
- Deployment produksi: `docs/DEPLOYMENT_GUIDE.md`
- Keamanan: `docs/SECURITY.md`
- Switch backend ML (RF/SVM): `docs/ML_BACKEND_SWITCH_GUIDE.md`
