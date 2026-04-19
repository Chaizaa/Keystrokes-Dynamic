# Keystroke Dynamics Blueprint Architecture (Current)

Dokumen ini merangkum struktur blueprint yang aktif pada codebase saat ini.

## 1. Struktur Routing

Blueprint yang diregistrasi di `app/__init__.py`:

- `main_bp` (tanpa prefix)
- `auth_bp` (tanpa prefix)
- `api_bp` (prefix `/api`)
- `admin_bp` (prefix `/admin`)
- `dataset_bp` (tanpa prefix, route `/dataset`)
- `health_bp` (prefix `/health`)

## 2. Struktur Folder Utama

```text
Keystrokes-Dynamic/
|- app/
|  |- __init__.py                 # create_app(), extension init, blueprint registration
|  |- blueprints/
|  |  |- main.py                  # /, /home, /dashboard/api-key
|  |  |- auth.py                  # /login, /register, /verify, reset pages
|  |  |- dataset.py               # /dataset page
|  |  |- health.py                # /health/* endpoints
|  |  |- admin.py                 # /admin/* endpoints
|  |  |- api/
|  |     |- __init__.py           # register submodules on api_bp
|  |     |- enrollment.py         # /check_username, /register_sample
|  |     |- login.py              # /pre_verify_password, /login, /verify_user
|  |     |- verification.py       # email verify + password reset verification flow
|  |     |- two_factor.py         # /2fa/enroll, /2fa/confirm, /2fa/verify
|  |     |- user.py               # /user/info, /user/reset_password
|  |     |- dataset.py            # /dataset/register|submit|status|export
|  |     |- _shared.py            # shared service objects + api_bp instance
|  |- models/                     # SQLAlchemy models
|  |- services/                   # auth/biometric/email services
|  |- utils/                      # keystroke feature extraction
|- templates/                     # Jinja templates
|- static/                        # JS/CSS assets
|- docs/                          # technical documentation
```

## 3. API Surface (Prefix `/api`)

### Enrollment and login
- `POST /api/check_username`
- `POST /api/register_sample`
- `POST /api/pre_verify_password`
- `POST /api/login`
- `POST /api/verify_user`

### User and account
- `GET /api/user/info` (requires login)
- `POST /api/user/reset_password` (requires login)

### Email verification and reset
- `POST /api/send_verification`
- `POST /api/verify_email`
- `POST /api/resend_verification`
- `POST /api/send_reset_verification`
- `POST /api/verify_reset`
- `POST /api/reset_password`

### Two-factor authentication
- `POST /api/2fa/enroll`
- `POST /api/2fa/confirm`
- `POST /api/2fa/verify`

### Dataset collection
- `POST /api/dataset/register`
- `POST /api/dataset/submit`
- `GET /api/dataset/status/<subject_code>`
- `GET /api/dataset/export`

## 4. Konfigurasi Runtime Penting

Variabel `.env` yang sering dipakai:

```env
FLASK_ENV=development
SECRET_KEY=replace-me

DATABASE_TYPE=sqlite
DATABASE_PATH=data/biometric_auth.db

RATELIMIT_ENABLED=True
DEV_LENIENT_RATELIMIT=True

ML_BACKEND=rf
# allowed: rf | svm
```

Catatan:
- `ML_BACKEND` dinormalisasi saat startup. Nilai invalid fallback ke `rf`.
- `api_bp` diexempt dari CSRF karena endpoint dipanggil via fetch/AJAX.

## 5. Operational Notes

- Gunakan `python run.py` untuk local run sederhana.
- Untuk migrasi schema, gunakan Alembic di folder `migrations/`.
- Untuk detail endpoint payload/response terbaru, gunakan `docs/API.md` sebagai rujukan utama.
