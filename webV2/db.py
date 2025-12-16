import sqlite3
import csv
import os
import json

class Database:
    def __init__(self, db_name="biometric_auth.db", csv_name="biometric_auth.csv"):
        self.db_path = os.path.abspath(db_name)
        self.csv_path = os.path.abspath(csv_name)

    # =========================================================================
    # FUNGSI UTAMA: MENYIMPAN DATA VEKTOR BIOMETRIK
    # =========================================================================
    def save_data(self, data_dict):
        """Menyimpan data vektor biometrik ke CSV dan SQLite."""
        print(f"\n[INFO] Menyimpan data ke: {self.db_path}")
        self._save_to_csv(data_dict)
        self._save_to_sqlite(data_dict)

    def _save_to_csv(self, data):
        file_exists = os.path.isfile(self.csv_path)
        try:
            # Convert ALL complex types to JSON strings before CSV writing
            csv_data = {}
            for k, v in data.items():
                # Handle semua data types yang bisa bikin masalah di CSV
                if isinstance(v, (list, dict, bool)) or v is None:
                    csv_data[k] = json.dumps(v)
                elif isinstance(v, (int, float)):
                    csv_data[k] = str(v)  # Convert ke string untuk safety
                else:
                    csv_data[k] = v
            
            with open(self.csv_path, mode='a', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=csv_data.keys())
                if not file_exists: writer.writeheader()
                writer.writerow(csv_data)
            print("[SUKSES] CSV Updated.")
        except PermissionError:
            print(f"[ERROR] Gagal menulis CSV! File '{self.csv_path}' sedang dibuka di Excel. Tutup dulu file tersebut.")
        except Exception as e:
            print(f"[ERROR] CSV: {e}")

    def _save_to_sqlite(self, data):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 1. Persiapkan Data (Konversi semua complex types ke JSON String agar bisa masuk DB)
        db_data = {}
        for k, v in data.items():
            # Handle semua data types yang bisa bikin masalah (SAMA DENGAN CSV!)
            if isinstance(v, (list, dict, bool)) or v is None:
                db_data[k] = json.dumps(v)
            elif isinstance(v, (int, float)):
                db_data[k] = str(v)  # Convert ke string untuk consistency dengan CSV
            else:
                db_data[k] = v

        table_name = "user_vectors"

        # 2. Cek Struktur Tabel & Tambah Kolom Otomatis (Schema Migration)
        try:
            # Cek kolom yang ada sekarang
            cursor.execute(f"PRAGMA table_info({table_name})")
            existing_columns = [row[1] for row in cursor.fetchall()]
            
            # Jika tabel belum ada, buat baru
            if not existing_columns:
                cols = []
                for k in db_data.keys():
                    cols.append(f"{k} TEXT")
                cols_str = ', '.join(cols)
                cursor.execute(f"CREATE TABLE {table_name} (id INTEGER PRIMARY KEY, {cols_str})")
            else:
                # Jika tabel sudah ada, cek apakah ada kolom baru yang perlu ditambah
                for key in db_data.keys():
                    if key not in existing_columns and key != 'id':
                        try:
                            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {key} TEXT")
                        except Exception:
                            pass # Abaikan jika gagal alter

            # 3. Insert Data
            placeholders = ', '.join(['?'] * len(db_data))
            columns = ', '.join(db_data.keys())
            values = list(db_data.values())
            
            cursor.execute(f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})", values)
            conn.commit()
            print("[SUKSES] SQLite Updated.")

        except Exception as e:
            print(f"[ERROR] SQLite Vector: {e}")
        finally:
            conn.close()

    # =========================================================================
    # FUNGSI GETTER: MENGAMBIL DATA UNTUK VERIFIKASI
    # =========================================================================
    def get_enrollment_samples(self, username):
        """Mengambil semua data sampel pendaftaran (HANYA ENROLLMENT!)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row # Agar hasil return berupa Dict
        cursor = conn.cursor()
        try:
            # [FIX] HANYA ambil data enrollment, bukan login attempt!
            # Ambil semua enrollment samples untuk training (no limit)
            cursor.execute("""
                SELECT * FROM user_vectors 
                WHERE username = ? AND data_type = 'enrollment'
                ORDER BY id DESC
            """, (username,))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"[DB ERROR] Get Enrollment: {e}")
            return []
        finally:
            conn.close()

    def get_user_data(self, username):
        """Mengambil 1 data enrollment terakhir (untuk profil tunggal)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM user_vectors WHERE username = ? ORDER BY id DESC LIMIT 1", (username,))
            row = cursor.fetchone()
            if row: return dict(row)
            return None
        except Exception as e:
            print(f"[ERROR] Get User: {e}")
            return None
        finally:
            conn.close()

    # =========================================================================
    # [DEV ONLY] - FITUR TAMBAHAN UNTUK MENYIMPAN PASSWORD ASLI
    # =========================================================================
    def save_dev_credentials(self, username, plain_password):
        """
        [HAPUS SAAT PRODUKSI]
        Menyimpan username dan password asli ke tabel 'users' untuk keperluan debugging.
        Berguna jika Anda lupa password saat masa pengembangan.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # 1. Buat tabel 'users' khusus dev jika belum ada
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    plain_password TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 2. Simpan / Update Password (Upsert sederhana)
            # Kita cek dulu apakah user sudah ada?
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            exists = cursor.fetchone()
            
            if exists:
                # Update password kalau user sudah ada
                cursor.execute("UPDATE users SET plain_password = ?, created_at = CURRENT_TIMESTAMP WHERE username = ?", (plain_password, username))
                print(f"[DEV MODE] Password asli untuk '{username}' diperbarui di tabel 'users'.")
            else:
                # Insert baru
                cursor.execute("INSERT INTO users (username, plain_password) VALUES (?, ?)", (username, plain_password))
                print(f"[DEV MODE] Password asli untuk '{username}' disimpan di tabel 'users'.")
            
            conn.commit()
        except Exception as e:
            print(f"[DEV ERROR] Gagal simpan password asli: {e}")
        finally:
            conn.close()