---

**Aplikasi                 : Keystrokes-Dynamic**

**Versi                     : 1.0.0**

**Modul                   : Admin User Management**

**Fungsi yang Diuji :**

a.	View User List - Menampilkan daftar pengguna dengan pagination (25 users per page)
b.	Create User - Membuat pengguna baru melalui form admin
c.	Send Password Reset - Mengirimkan link reset password ke email pengguna
d.	Delete User - Menghapus pengguna dan semua data biometrik terkait
e.	View Audit Logs - Menampilkan log audit aktivitas admin
f.	View System Diagnostics - Menampilkan informasi sistem dan status migrasi database

**Deskripsi :**

Modul yang digunakan untuk melakukan pengelolaan data pengguna pada aplikasi Keystrokes-Dynamic. Admin dapat melihat daftar pengguna, membuat pengguna baru, mengedit informasi pengguna (reset password), menghapus pengguna, melihat audit logs, dan melihat status sistem. Fitur keamanan meliputi pencegahan penghapusan admin terakhir, proteksi self-deletion, dan cascading data cleanup otomatis.

### Test Case

| No. | Tested Function | Procedure Test | Expected Result | Test Result | Test Explain |
|-----|-----------------|-----------------|-----------------|-------------|--------------|
| 1 | View User List | 1. Login sebagai admin<br>2. Akses halaman `/admin`<br>3. Lihat daftar pengguna | Data pengguna ditampilkan dengan pagination (25 users per page) | ☐ OK ☐ Not OK | |
| 2 | Create User | 1. Login sebagai admin<br>2. Buka `/admin/create`<br>3. Isi form username, email, password<br>4. Submit form | Data pengguna baru berhasil disimpan dan muncul di user list | ☐ OK ☐ Not OK | |
| 3 | Create User (Negative Case) | 1. Login sebagai admin<br>2. Buka `/admin/create`<br>3. Isi form dengan data invalid/duplikat<br>4. Submit form | Sistem menampilkan pesan error yang menjelaskan kesalahan input | ☐ OK ☐ Not OK | |
| 4 | Send Password Reset | 1. Login sebagai admin<br>2. Dari user list, klik tombol "Send Reset"<br>3. Konfirmasi pengiriman | Email reset password terkirim ke pengguna target | ☐ OK ☐ Not OK | |
| 5 | Delete User | 1. Login sebagai admin<br>2. Dari user list, klik tombol "Delete"<br>3. Konfirmasi penghapusan | Data pengguna dan semua data biometrik terhapus dari sistem | ☐ OK ☐ Not OK | |
| 6 | Delete User (Prevention) | 1. Login sebagai admin<br>2. Coba delete akun admin terakhir | Sistem mencegah penghapusan dan menampilkan pesan error | ☐ OK ☐ Not OK | |
| 7 | View Audit Logs | 1. Login sebagai admin<br>2. Lihat bagian "Audit Logs" di `/admin` | Log aktivitas admin ditampilkan dengan detail action, waktu, dan user | ☐ OK ☐ Not OK | |
| 8 | View System Diagnostics | 1. Login sebagai admin<br>2. Akses `/admin/diagnostics` | Informasi sistem (Alembic revision, migration status, DB columns) ditampilkan | ☐ OK ☐ Not OK | |

---

---

**Aplikasi                 : Keystrokes-Dynamic**

**Versi                     : 1.0.0**

**Modul                   : User Authentication**

**Fungsi yang Diuji :**

a.	Login - Melakukan autentikasi pengguna dengan verifikasi password dan keystroke dynamics
b.	Register - Melakukan pendaftaran pengguna baru dengan enrollment keystroke
c.	Email Verification - Memverifikasi email pengguna menggunakan 6-digit OTP code
d.	Password Reset Initiate - Memulai proses reset password dengan verifikasi kode dari email
e.	Password Reset Complete - Menyelesaikan reset password dengan enrollment keystroke baru
f.	Two-Factor Authentication - Mengirim dan memverifikasi kode 2FA via email
g.	Logout - Menutup session pengguna

**Deskripsi :**

Modul yang menangani proses autentikasi pengguna meliputi login, registrasi, password reset, dan verifikasi email. Mengintegrasikan keystroke dynamics sebagai layer keamanan tambahan di samping password tradisional. Sistem melindungi dengan OTP verification, session management yang aman, dan mendukung Two-Factor Authentication untuk keamanan ekstra.

### Test Case

| No. | Tested Function | Procedure Test | Expected Result | Test Result | Test Explain |
|-----|-----------------|-----------------|-----------------|-------------|--------------|
| 1 | Register User | 1. Akses halaman `/register`<br>2. Isi form username, email, password<br>3. Kumpulkan keystroke samples (enrollment)<br>4. Submit registrasi | Akun baru dibuat dan pengguna diminta verifikasi email | ☐ OK ☐ Not OK | |
| 2 | Register User (Negative Case) | 1. Akses halaman `/register`<br>2. Isi form dengan username duplikat/format invalid<br>3. Submit | Sistem menampilkan pesan error validasi | ☐ OK ☐ Not OK | |
| 3 | Email Verification | 1. Register pengguna baru<br>2. Buka email dan dapatkan kode OTP<br>3. Masukkan kode di halaman verifikasi | Email terverifikasi dan akun aktif | ☐ OK ☐ Not OK | |
| 4 | Email Verification (Invalid Code) | 1. Register pengguna baru<br>2. Masukkan kode OTP yang salah | Sistem menampilkan pesan error dan meminta kode ulang | ☐ OK ☐ Not OK | |
| 5 | Login (Valid Credentials) | 1. Akses halaman `/login`<br>2. Masukkan username dan password<br>3. Kumpulkan keystroke samples untuk verifikasi<br>4. Submit login | Login berhasil dan pengguna diarahkan ke dashboard | ☐ OK ☐ Not OK | |
| 6 | Login (Invalid Password) | 1. Akses halaman `/login`<br>2. Masukkan username dan password salah<br>3. Submit | Sistem menampilkan pesan error autentikasi gagal | ☐ OK ☐ Not OK | |
| 7 | Login (Keystroke Rejection) | 1. Akses halaman `/login`<br>2. Masukkan password benar<br>3. Kumpulkan keystroke dengan pola berbeda | Verifikasi keystroke gagal, login ditolak | ☐ OK ☐ Not OK | |
| 8 | Password Reset Initiate | 1. Akses halaman login<br>2. Klik "Forgot Password"<br>3. Masukkan email pengguna | Email reset password terkirim dengan kode verifikasi | ☐ OK ☐ Not OK | |
| 9 | Password Reset Complete | 1. Terima email reset password<br>2. Akses link/masukkan kode verifikasi<br>3. Set password baru dan kumpulkan keystroke baru<br>4. Submit | Password berhasil direset dan dapat login dengan password baru | ☐ OK ☐ Not OK | |
| 10 | Two-Factor Authentication | 1. Login dengan 2FA enabled<br>2. Setelah verifikasi password, masukkan kode 2FA dari email | Verifikasi 2FA berhasil dan pengguna dapat akses dashboard | ☐ OK ☐ Not OK | |
| 11 | Two-Factor Authentication (Wrong Code) | 1. Login dengan 2FA enabled<br>2. Masukkan kode 2FA yang salah | Sistem menampilkan pesan error dan meminta kode ulang | ☐ OK ☐ Not OK | |
| 12 | Logout | 1. Login berhasil<br>2. Klik tombol "Logout" | Session terminated dan pengguna diarahkan ke halaman login | ☐ OK ☐ Not OK | |

---

---

**Aplikasi                 : Keystrokes-Dynamic**

**Versi                     : 1.0.0**

**Modul                   : Main Dashboard & Public Pages**

**Fungsi yang Diuji :**

a.	Landing Page - Menampilkan halaman publik untuk pengguna yang belum login
b.	User Dashboard - Menampilkan dashboard pengguna yang sudah login dengan informasi profil
c.	View API Key - Menampilkan status API key pengguna untuk partner integration
d.	Generate API Key - Membuat atau regenerate API key untuk akses partner API

**Deskripsi :**

Modul yang menyediakan landing page publik, dashboard pengguna, dan manajemen API key untuk partner integration. Halaman publik dirancang user-friendly untuk menarik pengguna baru, sementara dashboard pengguna memberikan interface untuk manage akun dan API key. Semua API key ditampilkan hanya sekali untuk keamanan maksimal.

### Test Case

| No. | Tested Function | Procedure Test | Expected Result | Test Result | Test Explain |
|-----|-----------------|-----------------|-----------------|-------------|--------------|
| 1 | Access Landing Page | 1. Buka URL aplikasi root `/`<br>2. Lihat halaman publik | Landing page ditampilkan dengan call-to-action untuk login/register | ☐ OK ☐ Not OK | |
| 2 | Landing Page Redirect (Authenticated) | 1. Login sebagai pengguna<br>2. Akses `/`<br>3. Amati redirect | Pengguna yang authenticated diarahkan otomatis ke dashboard | ☐ OK ☐ Not OK | |
| 3 | Access User Dashboard | 1. Login sebagai pengguna<br>2. Akses `/dashboard` atau `/home` | Dashboard pengguna ditampilkan dengan informasi profil dan menu options | ☐ OK ☐ Not OK | |
| 4 | Dashboard Protection | 1. Logout pengguna<br>2. Coba akses `/dashboard` directly via URL | Sistem redirect ke halaman login (akses ditolak) | ☐ OK ☐ Not OK | |
| 5 | View API Key Status | 1. Login sebagai pengguna<br>2. Akses `/dashboard/api-key` | Halaman menampilkan status: "belum ada API key" atau API key yang sudah ada | ☐ OK ☐ Not OK | |
| 6 | Generate API Key | 1. Login sebagai pengguna<br>2. Akses `/dashboard/api-key`<br>3. Klik tombol "Generate"<br>4. Salin API key yang ditampilkan | API key baru berhasil digenerate dan ditampilkan sekali saja (tidak disimpan di layar) | ☐ OK ☐ Not OK | |
| 7 | Regenerate API Key | 1. Login dengan akun yang sudah punya API key<br>2. Akses `/dashboard/api-key`<br>3. Klik tombol "Regenerate"<br>4. Salin API key baru | API key lama invalidate dan API key baru digenerate | ☐ OK ☐ Not OK | |
| 8 | API Key Security | 1. Generate API key<br>2. Kembali ke halaman tanpa menyalin key<br>3. Refresh halaman | API key tidak ditampilkan lagi untuk keamanan | ☐ OK ☐ Not OK | |

---

---

**Aplikasi                 : Keystrokes-Dynamic**

**Versi                     : 1.0.0**

**Modul                   : Dataset Collection & Research**

**Fungsi yang Diuji :**

a.	Dataset Collection UI - Menampilkan halaman pengumpulan data keystroke untuk responden penelitian
b.	Dataset Registration - Melakukan registrasi responden baru untuk koleksi dataset
c.	Submit Keystroke Samples - Mengunggah keystroke samples untuk dataset penelitian
d.	Check Collection Status - Melihat progress pengumpulan sampel per responden
e.	Export Dataset - Mengekspor dataset dalam format CSV untuk analisis penelitian

**Deskripsi :**

Modul publik untuk pengumpulan data keystroke dynamics dari responden penelitian. Tidak memerlukan login dan dirancang untuk memudahkan peneliti mengumpulkan sampel keystroke dari partisipan secara otomatis. Sistem melacak progress, menghitung kualitas sample, dan menyediakan export functionality untuk analisis lebih lanjut.

### Test Case

| No. | Tested Function | Procedure Test | Expected Result | Test Result | Test Explain |
|-----|-----------------|-----------------|-----------------|-------------|--------------|
| 1 | Access Dataset Collection UI | 1. Buka URL `/dataset`<br>2. Lihat halaman pengumpulan data | Halaman dataset collection ditampilkan dengan form registrasi dan capture keystroke | ☐ OK ☐ Not OK | |
| 2 | Dataset Registration | 1. Akses `/dataset`<br>2. Isi form (nama, email, kategori)<br>3. Submit registrasi | Responden baru berhasil didaftarkan dan menerima session token | ☐ OK ☐ Not OK | |
| 3 | Dataset Registration (Duplicate) | 1. Register responden yang sama 2x<br>2. Submit form kedua kalinya | Sistem mengizinkan dan membuat session baru (multi-session support) | ☐ OK ☐ Not OK | |
| 4 | Submit Keystroke Samples | 1. Register di dataset collection<br>2. Capture keystroke samples dengan mengetik password<br>3. Submit samples | Keystroke samples berhasil disimpan dengan metadata (device, quality score) | ☐ OK ☐ Not OK | |
| 5 | Multiple Keystroke Sessions | 1. Submit samples pertama (e.g., 25 samples)<br>2. Kembali ke halaman dan submit samples kedua (e.g., 25 samples)<br>3. Ulangi hingga target tercapai | Setiap session samples ditambahkan ke total (multi-session tracking) | ☐ OK ☐ Not OK | |
| 6 | Check Collection Status | 1. Register responden<br>2. Submit beberapa samples<br>3. Akses `/api/dataset/status/<code>` | Status menampilkan: total samples, progress %, device info | ☐ OK ☐ Not OK | |
| 7 | Collection Completion | 1. Submit samples hingga mencapai target (default 100)<br>2. Lihat status atau hasil | Sistem menandai collection sebagai "complete" saat target tercapai | ☐ OK ☐ Not OK | |
| 8 | Export Dataset (CSV) | 1. Login sebagai admin (atau akses authorized)<br>2. Akses `/api/dataset/export`<br>3. Pilih format CSV<br>4. Download | Dataset berhasil diexport dalam format CSV dengan semua samples dan metadata | ☐ OK ☐ Not OK | |
| 9 | Export Dataset (Authorization) | 1. Akses `/api/dataset/export` tanpa authenticated admin<br>2. Coba download | Sistem menolak akses dan menampilkan error 403/401 | ☐ OK ☐ Not OK | |
| 10 | Sample Quality Assessment | 1. Submit keystroke samples dengan variasi kualitas<br>2. Amati quality score di system | Sistem memberikan quality score (bagus/cukup/buruk) berdasarkan timing features | ☐ OK ☐ Not OK | |

---

---

**Aplikasi                 : Keystrokes-Dynamic**

**Versi                     : 1.0.0**

**Modul                   : Biometric Verification API**

**Fungsi yang Diuji :**

a.	Check Username Availability - Mengecek ketersediaan username untuk registrasi
b.	Enroll Keystroke Samples - Mengirimkan keystroke samples untuk training model per-user
c.	Verify Login Keystroke - Memverifikasi keystroke saat proses login
d.	Send 2FA Code - Mengirimkan kode verifikasi 2FA via email
e.	Verify 2FA Code - Memverifikasi kode 2FA yang diterima
f.	Partner API Verification - Memverifikasi keystroke untuk partner integration (separate threshold)
g.	Get User Profile - Mengambil informasi profil pengguna yang authenticated
h.	Get Verification Statistics - Menampilkan statistik verifikasi pengguna

**Deskripsi :**

Modul API untuk enrollment dan verifikasi keystroke dynamics. Menyediakan endpoints untuk proses training model per-user, verifikasi login dengan biometrik keystroke, 2FA verification, dan partner API integration. Mendukung multiple machine learning backend (RandomForest, SVM, Statistical/Template Matching) dengan automatic model selection.

### Test Case

| No. | Tested Function | Procedure Test | Expected Result | Test Result | Test Explain |
|-----|-----------------|-----------------|-----------------|-------------|--------------|
| 1 | Check Username Availability | 1. Call API `/api/enrollment/check`<br>2. Submit username yang belum digunakan | API mengembalikan response: "available: true" | ☐ OK ☐ Not OK | |
| 2 | Check Username Availability (Taken) | 1. Call API `/api/enrollment/check`<br>2. Submit username yang sudah ada | API mengembalikan response: "available: false" | ☐ OK ☐ Not OK | |
| 3 | Enroll Keystroke Samples | 1. Call API `/api/enrollment/enroll`<br>2. Submit keystroke events dengan username<br>3. Lakukan beberapa kali hingga threshold | Model ML per-user berhasil ditraining | ☐ OK ☐ Not OK | |
| 4 | Enrollment Progress Tracking | 1. Submit keystroke samples bertahap<br>2. Query API untuk progress | API mengembalikan: total enrolled, recommended samples, login ready status | ☐ OK ☐ Not OK | |
| 5 | Verify Login Keystroke | 1. Pengguna sudah enrolled<br>2. Call API `/api/login/verify`<br>3. Submit password + keystroke events | Keystroke diverifikasi, similarity score > threshold = verified | ☐ OK ☐ Not OK | |
| 6 | Verify Login Keystroke (Rejection) | 1. Submit keystroke dengan pola berbeda jauh<br>2. Call verification API | Keystroke rejected, similarity score < threshold = failed | ☐ OK ☐ Not OK | |
| 7 | Send 2FA Code | 1. Call API `/api/two-factor/send`<br>2. Submit user_id/email | Kode 2FA (6 digit) terkirim ke email pengguna | ☐ OK ☐ Not OK | |
| 8 | Verify 2FA Code (Valid) | 1. Call API `/api/two-factor/verify`<br>2. Submit kode yang benar dari email | 2FA verification success, return session token | ☐ OK ☐ Not OK | |
| 9 | Verify 2FA Code (Invalid) | 1. Call API `/api/two-factor/verify`<br>2. Submit kode yang salah | Sistem menolak, return error "invalid code" | ☐ OK ☐ Not OK | |
| 10 | Partner API Verification | 1. Call `/api/partner/verify` dengan API key<br>2. Submit username + keystroke events<br>3. Use separate threshold (0.7) | Partner verification menggunakan statistical backend dan threshold yang berbeda | ☐ OK ☐ Not OK | |
| 11 | Get User Profile | 1. Call API `/api/user/profile` (authenticated)<br>2. Retrieve user data | API mengembalikan: username, email, enrollment status, 2FA enabled | ☐ OK ☐ Not OK | |
| 12 | Get Verification Statistics | 1. Call API `/api/verification/stats` (authenticated)<br>2. Retrieve stats | API mengembalikan: total logins, successful verifications, failed attempts | ☐ OK ☐ Not OK | |
| 13 | ML Backend Switching (RF/SVM/Statistical) | 1. Configure `ML_BACKEND=rf` (atau svm/statistical)<br>2. Perform enrollment dan login verification | Sistem menggunakan backend sesuai config tanpa error | ☐ OK ☐ Not OK | |
| 14 | API Rate Limiting | 1. Call API endpoint berulang kali dalam interval pendek<br>2. Exceed rate limit threshold | Sistem mengembalikan error 429 (Too Many Requests) | ☐ OK ☐ Not OK | |
| 15 | CSRF Protection Exemption | 1. Submit form POST ke API endpoint<br>2. Tanpa CSRF token | API tetap menerima request (CSRF exempted untuk API) | ☐ OK ☐ Not OK | |

---

---

**Aplikasi                 : Keystrokes-Dynamic**

**Versi                     : 1.0.0**

**Modul                   : System Health & Status Monitoring**

**Fungsi yang Diuji :**

a.	Liveness Probe - Mengecek apakah service sedang running (untuk health monitoring)
b.	Readiness Probe - Mengecek apakah service siap dan database connectivity
c.	Migration Status Check - Memverifikasi status migrasi database dan kolom yang diperlukan

**Deskripsi :**

Modul untuk monitoring kesehatan sistem, database connectivity, dan status migrasi. Dirancang untuk deployment health checks dan readiness probes di container/Kubernetes environment. Menyediakan detailed error responses untuk troubleshooting deployment issues tanpa memerlukan authentication.

### Test Case

| No. | Tested Function | Procedure Test | Expected Result | Test Result | Test Explain |
|-----|-----------------|-----------------|-----------------|-------------|--------------|
| 1 | Liveness Probe (Service Running) | 1. Call GET `/health/live`<br>2. Amati response | API mengembalikan HTTP 200 dengan status "ok" | ☐ OK ☐ Not OK | |
| 2 | Liveness Probe (Service Down) | 1. Stop Flask application<br>2. Try call `/health/live` | Connection refused atau 0 response (service down) | ☐ OK ☐ Not OK | |
| 3 | Readiness Probe (DB Connected) | 1. Ensure database running<br>2. Call GET `/health/ready` | API mengembalikan HTTP 200 dengan status "ok", message "service is ready" | ☐ OK ☐ Not OK | |
| 4 | Readiness Probe (DB Disconnected) | 1. Stop database service<br>2. Call GET `/health/ready` | API mengembalikan HTTP 503 dengan status "error", message menunjukkan DB not ready | ☐ OK ☐ Not OK | |
| 5 | Migration Status Check | 1. Call GET `/health/migrations`<br>2. Ensure migrations up-to-date | API mengembalikan HTTP 200 dengan "required_user_columns_present: true" | ☐ OK ☐ Not OK | |
| 6 | Migration Status (Missing Columns) | 1. Manually drop required column dari DB<br>2. Call `/health/migrations` | API mengembalikan HTTP 503 dengan "required_user_columns_present: false" dan detail | ☐ OK ☐ Not OK | |
| 7 | Alembic Version Info | 1. Call `/health/migrations`<br>2. Check `alembic_revision` field | API menampilkan Alembic version number (e.g., "abc123def") | ☐ OK ☐ Not OK | |
| 8 | No Authentication Required | 1. Call `/health/live`, `/health/ready`, `/health/migrations` tanpa login<br>2. Amati response | Semua endpoint accessible tanpa authentication | ☐ OK ☐ Not OK | |
| 9 | Health Check Response Format | 1. Call any health endpoint<br>2. Parse JSON response | Response berformat JSON dengan field: status, message, dan detail tambahan | ☐ OK ☐ Not OK | |

---

---

**Aplikasi                 : Keystrokes-Dynamic**

**Versi                     : 1.0.0**

**Modul                   : Notification Management**

**Fungsi yang Diuji :**

a.	Send Email Notification - Mengirimkan notifikasi via email (verification, reset password, alerts)
b.	View Notification History - Melihat riwayat notifikasi yang diterima
c.	Notification Preferences - Mengatur preferensi jenis notifikasi yang diterima
d.	Mark Notification as Read - Menandai notifikasi yang sudah dibaca
e.	Delete Notification - Menghapus notifikasi dari history
f.	Email Verification Notification - Notifikasi untuk verifikasi email baru
g.	Login Alert Notification - Notifikasi alert saat ada login baru
h.	Admin Action Notification - Notifikasi untuk admin actions (user deleted, password reset, dll)

**Deskripsi :**

Modul untuk mengelola sistem notifikasi pengguna termasuk email notifications, in-app alerts, dan notification history. Sistem ini memungkinkan pengguna mengatur preferensi notifikasi dan melacak semua notifikasi yang diterima. Admin dapat mengirimkan notification khusus untuk aktivitas sistem penting seperti password reset, user deletion, dan login alerts untuk keamanan ekstra.

### Test Case

| No. | Tested Function | Procedure Test | Expected Result | Test Result | Test Explain |
|-----|-----------------|-----------------|-----------------|-------------|--------------|
| 1 | Send Email Verification | 1. Register pengguna baru<br>2. System kirim verification email<br>3. Cek inbox email | Email verifikasi terkirim dengan OTP code 6 digit | ☐ OK ☐ Not OK | |
| 2 | Send Password Reset Notification | 1. Admin trigger password reset untuk user<br>2. Cek email user | Email reset password terkirim dengan link/token | ☐ OK ☐ Not OK | |
| 3 | Login Alert Notification | 1. User login dari device/IP baru<br>2. Cek email untuk alert login | Email alert dikirim berisi: device info, IP address, timestamp | ☐ OK ☐ Not OK | |
| 4 | Admin Action Notification | 1. Admin delete user / reset password<br>2. Notification di-log di system | Admin action notification tercatat dengan detail action | ☐ OK ☐ Not OK | |
| 5 | View Notification History | 1. Login sebagai pengguna<br>2. Akses notification history page<br>3. Lihat daftar notifikasi | History notifikasi ditampilkan dengan tanggal, type, dan status read/unread | ☐ OK ☐ Not OK | |
| 6 | Notification Pagination | 1. Lihat notification history<br>2. Amati pagination (jika >25 items) | Notifikasi di-paginate dengan 25 items per page | ☐ OK ☐ Not OK | |
| 7 | Mark Notification as Read | 1. Lihat unread notification<br>2. Klik "Mark as Read"<br>3. Amati perubahan status | Status notification berubah dari unread ke read | ☐ OK ☐ Not OK | |
| 8 | Mark All as Read | 1. Ada multiple unread notifications<br>2. Klik "Mark All as Read" | Semua notifikasi ditandai read sekaligus | ☐ OK ☐ Not OK | |
| 9 | Delete Single Notification | 1. Lihat notification history<br>2. Klik delete pada satu notifikasi<br>3. Konfirmasi | Notifikasi terhapus dari history | ☐ OK ☐ Not OK | |
| 10 | Delete All Notifications | 1. Lihat notification history<br>2. Klik "Delete All"<br>3. Konfirmasi | Semua notifikasi dihapus sekaligus | ☐ OK ☐ Not OK | |
| 11 | Notification Preferences - Email | 1. Login sebagai pengguna<br>2. Akses settings/preferences<br>3. Toggle email notification on/off | Preferensi notifikasi email disimpan | ☐ OK ☐ Not OK | |
| 12 | Notification Preferences - Alert Types | 1. Akses notification preferences<br>2. Select notification types: security alerts, login alerts, admin messages<br>3. Save | Preferensi jenis notifikasi disimpan sesuai pilihan | ☐ OK ☐ Not OK | |
| 13 | Notification Filtering | 1. Lihat notification history<br>2. Filter by type (verification, security, admin)<br>3. Amati hasil filter | Notifikasi di-filter sesuai type yang dipilih | ☐ OK ☐ Not OK | |
| 14 | Email Template Verification | 1. Trigger berbagai jenis notifikasi (verify, reset, alert)<br>2. Cek format email | Setiap notifikasi punya template yang jelas, profesional, dan informatif | ☐ OK ☐ Not OK | |
| 15 | Unread Count Badge | 1. Ada unread notifications<br>2. Lihat badge di notification icon/menu | Badge menampilkan jumlah unread notifications | ☐ OK ☐ Not OK | |

---

---

**Aplikasi                 : Keystrokes-Dynamic**

**Versi                     : 1.0.0**

**Modul                   : Role & Permission Management**

**Fungsi yang Diuji :**

a.	View User Roles - Menampilkan role yang dimiliki setiap pengguna
b.	Assign Role to User - Memberikan role tertentu kepada pengguna
c.	Change User Role - Mengubah role pengguna dari satu role ke role lain
d.	View Role Permissions - Melihat daftar permissions untuk setiap role
e.	Create Custom Role - Membuat custom role dengan granular permissions
f.	Delete Role - Menghapus role yang sudah tidak digunakan
g.	Check User Permission - Verifikasi apakah user punya permission untuk aksi tertentu
h.	Audit Role Changes - Melihat history perubahan role pengguna

**Deskripsi :**

Modul untuk mengelola sistem role dan permission yang lebih granular di aplikasi. Mendukung role default (admin, user) dan custom roles dengan permissions yang dapat dikonfigurasi. Admin dapat mengassign role, membuat role baru, dan melacak semua perubahan role untuk keperluan audit dan compliance. Sistem memverifikasi permission saat user melakukan aksi yang memerlukan privilege khusus.

### Test Case

| No. | Tested Function | Procedure Test | Expected Result | Test Result | Test Explain |
|-----|-----------------|-----------------|-----------------|-------------|--------------|
| 1 | View Default Roles | 1. Login sebagai admin<br>2. Akses role management page<br>3. Lihat daftar role default | Role default ditampilkan: admin, user, dengan permissions | ☐ OK ☐ Not OK | |
| 2 | View User Roles | 1. Login sebagai admin<br>2. Buka user list<br>3. Lihat role untuk setiap user | Setiap user menampilkan role yang dimiliki | ☐ OK ☐ Not OK | |
| 3 | Assign Role to User | 1. Login sebagai admin<br>2. Pilih user dari list<br>3. Klik "Assign Role"<br>4. Pilih role dan save | Role berhasil di-assign, user mendapat permissions sesuai role | ☐ OK ☐ Not OK | |
| 4 | Change User Role | 1. Login sebagai admin<br>2. Pilih user dengan role "user"<br>3. Change ke role "admin" (atau custom role)<br>4. Save | Role berhasil diubah, audit log tercatat | ☐ OK ☐ Not OK | |
| 5 | View Role Permissions | 1. Login sebagai admin<br>2. Buka role management<br>3. Klik role untuk melihat permissions | Detail permissions ditampilkan: view_users, edit_users, delete_users, dll | ☐ OK ☐ Not OK | |
| 6 | Admin Role Permissions | 1. View permissions untuk role "admin" | Admin role punya full permissions: view_users, create_users, edit_users, delete_users, manage_roles, manage_permissions | ☐ OK ☐ Not OK | |
| 7 | User Role Permissions | 1. View permissions untuk role "user" | User role punya limited permissions: view_profile, edit_profile, view_dashboard | ☐ OK ☐ Not OK | |
| 8 | Create Custom Role | 1. Login sebagai admin<br>2. Klik "Create New Role"<br>3. Isi nama role (e.g., "manager")<br>4. Select permissions<br>5. Save | Custom role berhasil dibuat dengan permissions yang dipilih | ☐ OK ☐ Not OK | |
| 9 | Custom Role with Partial Permissions | 1. Create custom role "auditor"<br>2. Assign permissions: view_users, view_audit_logs<br>3. Disable: create_users, delete_users<br>4. Assign ke user<br>5. Test akses | User auditor dapat view tapi tidak bisa create/delete | ☐ OK ☐ Not OK | |
| 10 | Edit Custom Role Permissions | 1. Buka custom role<br>2. Ubah permission (add/remove)<br>3. Save<br>4. Amati perubahan untuk user dengan role ini | Permission changes diterapkan ke semua user dengan role ini | ☐ OK ☐ Not OK | |
| 11 | Delete Custom Role | 1. Login sebagai admin<br>2. Buka custom role<br>3. Klik "Delete Role"<br>4. Konfirmasi | Custom role dihapus, user dengan role ini di-reassign ke default role | ☐ OK ☐ Not OK | |
| 12 | Cannot Delete Default Roles | 1. Coba delete role "admin" atau "user"<br>2. Amati response | Sistem mencegah penghapusan default roles dengan error message | ☐ OK ☐ Not OK | |
| 13 | Permission Check on Action | 1. Login sebagai user dengan role "user"<br>2. Coba akses admin page<br>3. Coba delete user | Sistem menolak akses dengan error 403 (Forbidden) | ☐ OK ☐ Not OK | |
| 14 | Admin Can Access All | 1. Login sebagai admin<br>2. Akses semua admin features (user management, role management, audit logs)<br>3. Perform semua actions | Admin dapat akses dan perform semua actions tanpa restriction | ☐ OK ☐ Not OK | |
| 15 | Audit Role Changes | 1. Admin assign role ke user<br>2. Admin change user role<br>3. Akses audit logs | Semua role changes tercatat dengan: who changed, what changed, when | ☐ OK ☐ Not OK | |
| 16 | Role Change Notification | 1. Admin assign role baru ke user<br>2. Cek email/notification user | User menerima notification tentang role change | ☐ OK ☐ Not OK | |
| 17 | Permission Inheritance | 1. Create hierarchy role (e.g., manager inherits from user permissions)<br>2. Assign ke user<br>3. Test permissions | User dengan manager role punya user permissions + additional manager permissions | ☐ OK ☐ Not OK | |

---

## ARCHITECTURE & TECHNICAL DETAILS

| Tabel Utama | Fungsi |
|-------------|--------|
| `users` | Penyimpanan data pengguna (username, email, password hash, 2FA status) |
| `users_vector` | Keystroke samples (raw biometric data) |
| `user_ml_model` | Per-user trained ML models |
| `admin_audit` | Audit log aktivitas admin |
| `enrollment_log` | Log proses enrollment keystroke |
| `verification_log` | Log proses verifikasi keystroke |
| `login_attempt` | Tracking attempt login per user |
| `api_key` | API keys untuk partner integration |
| `dataset` | Collected keystroke samples untuk research |

---

## TECHNICAL REFERENCE

**Technology Stack:**
- Web Framework: Flask 2.x
- Database ORM: SQLAlchemy + Flask-Migrate
- ML Backend: scikit-learn (RandomForest, SVM, Statistical)
- Database: SQLite (default) / PostgreSQL
- Authentication: Flask-Login + JWT
- Security: Werkzeug, Talisman, Flask-CORS
- Python Version: 3.12+

**Key Configuration:**
- ML_BACKEND: rf (RandomForest) / svm / statistical
- VERIFICATION_THRESHOLD: 0.7 (internal users)
- PARTNER_DECISION_THRESHOLD: 0.7 (partner API)
- DATABASE_TYPE: sqlite / postgresql

**Deployment Options:**
- Local development (Flask)
- Docker (docker-compose)
- Railway/Heroku (with gunicorn)
- Kubernetes (health check endpoints provided)

---

**Document Version:** 1.0  
**Last Updated:** June 5, 2026

---

## SUMMARY

**Total Modules:** 8  
**Total Test Cases:** 117

| No. | Module | Test Cases |
|-----|--------|-----------|
| 1 | Admin User Management | 8 |
| 2 | User Authentication | 12 |
| 3 | Main Dashboard & Public Pages | 8 |
| 4 | Dataset Collection & Research | 10 |
| 5 | Biometric Verification API | 15 |
| 6 | System Health & Status Monitoring | 9 |
| 7 | Notification Management | 15 |
| 8 | Role & Permission Management | 17 |
| **TOTAL** | | **94** |

---

**Status:** Ready for Quality Assurance Testing  
**Repository:** `update_apis` branch
