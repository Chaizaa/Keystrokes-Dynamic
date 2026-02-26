"""Legacy database helper — DEPRECATED.

.. deprecated::
    This module wraps raw SQLite/CSV access.
    New code should use SQLAlchemy models from ``app.models`` instead.
    See ``app/database/db.py`` for the app-level wrapper.
    This file is retained only for backward-compatibility with legacy scripts.
"""
import csv
import json
import os
import sqlite3
from config import basedir, Config


class Database:
    def __init__(self, db_name=None, csv_name=None):
        # Resolve defaults from config when not provided
        if db_name is None:
            db_name = os.path.join(basedir, Config.DATABASE_PATH)
        if csv_name is None:
            csv_name = os.path.join(os.path.dirname(db_name) or basedir, "biometric_auth.csv")

        # Ensure data directory exists
        data_dir = os.path.dirname(db_name)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
            print(f"[INFO] Created directory: {data_dir}")

        self.db_path = os.path.abspath(db_name)
        self.csv_path = os.path.abspath(csv_name)

        # Ensure password_hash column exists in users table
        self._migrate_users_table()

    def _migrate_users_table(self):
        """Migrate users table to add password_hash column if missing"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # Create users table if not exists
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    password_hash TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Check if password_hash column exists
            cursor.execute("PRAGMA table_info(users)")
            columns = [row[1] for row in cursor.fetchall()]

            # Add password_hash column if missing (for legacy users)
            if "password_hash" not in columns:
                print("[MIGRATION] Adding password_hash column to users table...")
                cursor.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
                conn.commit()
                print("[MIGRATION] ✅ password_hash column added successfully!")

        except Exception as e:
            print(f"[MIGRATION ERROR] {e}")
        finally:
            conn.close()

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

            with open(self.csv_path, mode="a", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=csv_data.keys())
                if not file_exists:
                    writer.writeheader()
                writer.writerow(csv_data)
            print("[SUCCESS] CSV Updated.")
        except PermissionError:
            print(
                f"[ERROR] Failed to write CSV! File '{self.csv_path}' appears to be open (e.g. in Excel). Close it and try again."
            )
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

        # Add timestamp if not present
        if "timestamp" not in db_data:
            db_data["timestamp"] = None  # Will use CURRENT_TIMESTAMP default

        # Add password column if exists in data but not in db_data
        if "password" not in db_data and "real_password_string" in data:
            db_data["password"] = data["real_password_string"]

        table_name = "user_vectors"

        # 2. Cek Struktur Tabel & Tambah Kolom Otomatis (Schema Migration)
        try:
            # Cek kolom yang ada sekarang
            cursor.execute(f"PRAGMA table_info({table_name})")
            existing_columns = [row[1] for row in cursor.fetchall()]

            # Jika tabel belum ada, buat baru dengan struktur lengkap
            if not existing_columns:
                cursor.execute(
                    f"""
                    CREATE TABLE {table_name} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT,
                        data_type TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        password TEXT,
                        H_vector TEXT,
                        DD_vector TEXT,
                        UD_vector TEXT,
                        UU_vector TEXT,
                        DU_vector TEXT,
                        H_stats TEXT,
                        DD_stats TEXT,
                        UD_stats TEXT,
                        char_count TEXT,
                        total_duration TEXT,
                        typing_rollover_ratio TEXT,
                        backspace_count TEXT,
                        char_sequence TEXT,
                        masked_sequence TEXT,
                        quality_label TEXT,
                        quality_score TEXT,
                        password_strength TEXT,
                        password_score TEXT
                    )
                """
                )
                print(f"[MIGRATION] Created {table_name} table with complete structure")
            else:
                # Ensure timestamp column exists
                if "timestamp" not in existing_columns:
                    cursor.execute(
                        f"ALTER TABLE {table_name} ADD COLUMN timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                    )
                    print("[MIGRATION] Added timestamp column to user_vectors")

                # Jika tabel sudah ada, cek apakah ada kolom baru yang perlu ditambah
                for key in db_data.keys():
                    if key not in existing_columns and key != "id":
                        try:
                            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {key} TEXT")
                        except Exception:
                            pass  # Abaikan jika gagal alter

            # 3. Insert Data
            placeholders = ", ".join(["?"] * len(db_data))
            columns = ", ".join(db_data.keys())
            values = list(db_data.values())

            cursor.execute(f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})", values)
            conn.commit()
            print("[SUCCESS] SQLite Updated.")

        except Exception as e:
            print(f"[ERROR] SQLite Vector: {e}")
        finally:
            conn.close()

    # =========================================================================
    # FUNGSI GETTER: MENGAMBIL DATA UNTUK VERIFIKASI
    # =========================================================================
    def get_enrollment_samples(self, username):
        """
        Mengambil semua data sampel pendaftaran (HANYA ENROLLMENT!)
        Supports backward compatibility: enrollment_vectors (new) > user_vectors (old)
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Agar hasil return berupa Dict
        cursor = conn.cursor()
        try:
            # Try new table first (enrollment_vectors)
            try:
                cursor.execute(
                    """
                    SELECT * FROM enrollment_vectors 
                    WHERE username = ?
                    ORDER BY id DESC
                """,
                    (username,),
                )

                rows = cursor.fetchall()

                if rows:
                    print(f"[DB] Loaded {len(rows)} samples from enrollment_vectors (new table)")
                    # Parse JSON strings to Python objects
                    parsed_rows = []
                    for row in rows:
                        row_dict = dict(row)
                        # Parse vector columns from JSON strings to lists
                        for key in [
                            "H_vector",
                            "DD_vector",
                            "UD_vector",
                            "UU_vector",
                            "DU_vector",
                        ]:
                            if key in row_dict and isinstance(row_dict[key], str):
                                try:
                                    row_dict[key] = json.loads(row_dict[key])
                                except Exception:
                                    row_dict[key] = []
                        # Parse stats columns from JSON strings to dicts
                        for key in ["H_stats", "DD_stats", "UD_stats"]:
                            if key in row_dict and isinstance(row_dict[key], str):
                                try:
                                    row_dict[key] = json.loads(row_dict[key])
                                except Exception:
                                    row_dict[key] = {}
                        parsed_rows.append(row_dict)
                    return parsed_rows
            except sqlite3.OperationalError:
                # Table doesn't exist yet, fallback to old table
                print("[DB] enrollment_vectors not found, using user_vectors (old table)")

            # Fallback to old table (user_vectors)
            cursor.execute(
                """
                SELECT * FROM user_vectors 
                WHERE username = ? AND data_type = 'enrollment'
                ORDER BY id DESC
            """,
                (username,),
            )

            rows = cursor.fetchall()
            print(f"[DB] Loaded {len(rows)} samples from user_vectors (old table)")

            # Parse JSON strings to Python objects
            parsed_rows = []
            for row in rows:
                row_dict = dict(row)
                # Parse vector columns from JSON strings to lists
                for key in [
                    "H_vector",
                    "DD_vector",
                    "UD_vector",
                    "UU_vector",
                    "DU_vector",
                ]:
                    if key in row_dict and isinstance(row_dict[key], str):
                        try:
                            row_dict[key] = json.loads(row_dict[key])
                        except Exception:
                            row_dict[key] = []
                # Parse stats columns from JSON strings to dicts
                for key in ["H_stats", "DD_stats", "UD_stats"]:
                    if key in row_dict and isinstance(row_dict[key], str):
                        try:
                            row_dict[key] = json.loads(row_dict[key])
                        except Exception:
                            row_dict[key] = {}
                parsed_rows.append(row_dict)

            return parsed_rows

        except Exception as e:
            print(f"[DB ERROR] Get Enrollment: {e}")
            import traceback

            traceback.print_exc()
            return []
        finally:
            conn.close()

    def get_user_data(self, username):
        """Mengambil 1 data enrollment terakhir (untuk profil tunggal)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT * FROM user_vectors WHERE username = ? ORDER BY id DESC LIMIT 1",
                (username,),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        except Exception as e:
            print(f"[ERROR] Get User: {e}")
            return None
        finally:
            conn.close()

    def get_enrollment_count(self, username):
        """
        Get jumlah enrollment samples untuk user
        Supports backward compatibility: enrollment_vectors (new) > user_vectors (old)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # Try new table first (enrollment_vectors)
            try:
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM enrollment_vectors 
                    WHERE username = ?
                """,
                    (username,),
                )
                count = cursor.fetchone()[0]

                if count > 0:
                    print(f"[DB] Enrollment count from enrollment_vectors: {count}")
                    return count
            except sqlite3.OperationalError:
                # Table doesn't exist, fallback to old table
                pass

            # Fallback to old table (user_vectors) - support both event_type and legacy data_type
            try:
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM user_vectors 
                    WHERE username = ? AND (event_type = 'enrollment' OR data_type = 'enrollment')
                """,
                    (username,),
                )
                count = cursor.fetchone()[0]
                print(f"[DB] Enrollment count from user_vectors: {count}")
                return count
            except sqlite3.OperationalError:
                # Column doesn't exist in legacy schema, try legacy column name
                try:
                    cursor.execute(
                        """
                        SELECT COUNT(*) FROM user_vectors 
                        WHERE username = ? AND data_type = 'enrollment'
                    """,
                        (username,),
                    )
                    count = cursor.fetchone()[0]
                    print(f"[DB] Enrollment count (legacy data_type) from user_vectors: {count}")
                    return count
                except Exception:
                    return 0

        except Exception as e:
            print(f"[DB ERROR] Get Enrollment Count: {e}")
            import traceback

            traceback.print_exc()
            return 0
        finally:
            conn.close()

    def get_login_count(self, username):
        """Get jumlah login samples untuk username tertentu"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # Prefer event_type if present
            try:
                cursor.execute(
                    """
                    SELECT COUNT(*) 
                    FROM user_vectors 
                    WHERE username = ? AND (event_type = 'login' OR data_type = 'login')
                """,
                    (username,),
                )
                count = cursor.fetchone()[0]
                return count
            except sqlite3.OperationalError:
                # Fallback to legacy data_type column
                try:
                    cursor.execute(
                        """
                        SELECT COUNT(*) 
                        FROM user_vectors 
                        WHERE username = ? AND data_type = 'login'
                    """,
                        (username,),
                    )
                    count = cursor.fetchone()[0]
                    return count
                except Exception:
                    return 0
        except Exception as e:
            print(f"[DB ERROR] Get Login Count: {e}")
            return 0
        finally:
            conn.close()

    def get_user_by_username(self, username):
        """
        Get user data from users table with fallback to user_vectors

        Args:
            username: Username to lookup

        Returns:
            Dictionary with user data or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # Try users table first (new architecture)
            cursor.execute(
                """
                SELECT username, created_at as last_login
                FROM users 
                WHERE username = ?
            """,
                (username,),
            )

            row = cursor.fetchone()
            if row:
                return dict(row)

            # Fallback to user_vectors table (legacy)
            print(f"[DB] User not found in users table, checking user_vectors for {username}")
            cursor.execute(
                """
                SELECT DISTINCT 
                    username, 
                    MAX(timestamp) as last_login
                FROM user_vectors 
                WHERE username = ?
                GROUP BY username
            """,
                (username,),
            )

            row = cursor.fetchone()
            if row:
                return dict(row)

            return None

        except Exception as e:
            print(f"[DB ERROR] Get user by username: {e}")
            return None
        finally:
            conn.close()

    # =========================================================================
    # [DEV ONLY] - FITUR TAMBAHAN UNTUK MENYIMPAN PASSWORD ASLI
    # =========================================================================
    def save_dev_credentials(self, username, plain_password=None, password_hash=None):
        """
        .. deprecated::
            Storing plain-text passwords is a security risk and no longer supported.
            Use ``auth_service.create_user`` + bcrypt hashing instead.
            This method now stores only the password_hash and ignores plain_password.
        """
        import warnings
        warnings.warn(
            "save_dev_credentials stores plain-text passwords and is deprecated. "
            "Use AuthService.create_user() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if plain_password is not None:
            plain_password = None  # Never persist plain-text passwords
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # 1. Buat tabel 'users' dengan kolom password_hash
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    password_hash TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # 2. Simpan / Update Password (Upsert sederhana)
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            exists = cursor.fetchone()

            if exists:
                if password_hash:
                    cursor.execute(
                        "UPDATE users SET password_hash = ?, created_at = CURRENT_TIMESTAMP WHERE username = ?",
                        (password_hash, username),
                    )
                    print(f"[DEV MODE] Password hash untuk '{username}' diperbarui di tabel 'users'.")
            else:
                if password_hash:
                    cursor.execute(
                        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                        (username, password_hash),
                    )
                else:
                    cursor.execute(
                        "INSERT INTO users (username) VALUES (?)",
                        (username,),
                    )
                print(f"[DEV MODE] User '{username}' disimpan di tabel 'users'.")

            conn.commit()
        except Exception as e:
            print(f"[DEV ERROR] Gagal simpan password asli: {e}")
        finally:
            conn.close()

    def get_password_hash(self, username):
        """Mengambil password hash untuk pre-verification"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
            result = cursor.fetchone()
            return result[0] if result else None
        except Exception as e:
            print(f"[DB ERROR] Get Password Hash: {e}")
            return None
        finally:
            conn.close()

    # =========================================================================
    # UNIFIED LOGIN FUNCTIONS
    # =========================================================================

    def get_enrollment_samples_from_new_table(self, username):
        """Get enrollment samples from enrollment_vectors table (NEW)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT * FROM enrollment_vectors
                WHERE username = ?
                ORDER BY id DESC
            """,
                (username,),
            )

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        except Exception as e:
            print(f"[DB ERROR] Get enrollment from new table: {e}")
            # Fallback to old method if new table doesn't exist
            return self.get_enrollment_samples(username)
        finally:
            conn.close()

    def save_verified_login(self, login_data):
        """Save verified login attempt to verified_logins table"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Ensure verified_logins table exists
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS verified_logins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT,
                    password_hash TEXT,
                    timestamp TIMESTAMP,
                    H_vector TEXT,
                    DD_vector TEXT,
                    UD_vector TEXT,
                    verification_score REAL,
                    recommended_method TEXT,
                    ip_address TEXT,
                    user_agent TEXT
                )
            """
            )

            # Convert complex types to JSON
            db_data = {}
            for key, value in login_data.items():
                if isinstance(value, (list, dict)):
                    db_data[key] = json.dumps(value)
                else:
                    db_data[key] = value

            # Build INSERT query safely
            columns = []
            values = []
            for key, value in db_data.items():
                columns.append(key)
                values.append(value)

            placeholders = ", ".join(["?"] * len(values))
            columns_str = ", ".join(columns)

            query = f"INSERT INTO verified_logins ({columns_str}) VALUES ({placeholders})"
            cursor.execute(query, values)

            conn.commit()
            print(
                f"[DB] Verified login saved: {login_data.get('username')} at {login_data.get('timestamp')}"
            )
            return True

        except Exception as e:
            print(f"[DB ERROR] Failed to save verified login: {e}")
            import traceback

            traceback.print_exc()
            return False
        finally:
            conn.close()

    def log_failed_login(
        self,
        username,
        failure_reason,
        ip_address=None,
        user_agent=None,
        verification_score=None,
    ):
        """Log failed login attempt (NO keystroke data saved for security)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO failed_logins 
                (username, failure_reason, verification_score, ip_address, user_agent, timestamp)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (username, failure_reason, verification_score, ip_address, user_agent),
            )

            conn.commit()
            print(f"[SECURITY LOG] Failed login: {username} - {failure_reason}")
            return True

        except Exception as e:
            print(f"[DB ERROR] Failed to log failed login: {e}")
            return False
        finally:
            conn.close()

    def get_verified_login_count(self, username):
        """Get count of verified logins for adaptive learning"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # First try verified_logins table
            cursor.execute(
                """
                SELECT COUNT(*) FROM verified_logins
                WHERE username = ?
            """,
                (username,),
            )

            count = cursor.fetchone()[0]

            # If zero, try user_vectors with data_type='login' as fallback
            if count == 0:
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM user_vectors
                    WHERE username = ? AND data_type = 'login'
                """,
                    (username,),
                )
                count = cursor.fetchone()[0]

            return count

        except Exception as e:
            print(f"[DB ERROR] Get verified login count: {e}")
            return 0
        finally:
            conn.close()

    def get_failed_login_count_recent(self, username, minutes=15):
        """Get count of recent failed login attempts (for rate limiting)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT COUNT(*) FROM failed_logins
                WHERE username = ? 
                AND timestamp > datetime('now', '-' || ? || ' minutes')
            """,
                (username, minutes),
            )

            count = cursor.fetchone()[0]
            return count

        except Exception as e:
            print(f"[DB ERROR] Get recent failed login count: {e}")
            return 0
        finally:
            conn.close()

    def cleanup_old_verified_logins(self, days=30):
        """Delete verified logins older than N days (data retention policy)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                DELETE FROM verified_logins
                WHERE timestamp < datetime('now', '-' || ? || ' days')
            """,
                (days,),
            )

            deleted_count = cursor.rowcount
            conn.commit()
            print(f"[DB CLEANUP] Deleted {deleted_count} old verified logins (>{days} days)")
            return deleted_count

        except Exception as e:
            print(f"[DB ERROR] Cleanup failed: {e}")
            return 0
        finally:
            conn.close()

    def cleanup_old_failed_logins(self, days=7):
        """Delete failed logins older than N days (security log retention)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                DELETE FROM failed_logins
                WHERE timestamp < datetime('now', '-' || ? || ' days')
            """,
                (days,),
            )

            deleted_count = cursor.rowcount
            conn.commit()
            print(f"[DB CLEANUP] Deleted {deleted_count} old failed logins (>{days} days)")
            return deleted_count

        except Exception as e:
            print(f"[DB ERROR] Cleanup failed: {e}")
            return 0
        finally:
            conn.close()

    def aggregate_login_statistics(self):
        """Aggregate verified logins to daily statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Aggregate to login_statistics table
            cursor.execute(
                """
                INSERT OR REPLACE INTO login_statistics 
                (username, date, login_count, avg_score, failed_count)
                SELECT 
                    v.username,
                    DATE(v.timestamp) as date,
                    COUNT(v.id) as login_count,
                    AVG(v.verification_score) as avg_score,
                    COALESCE((
                        SELECT COUNT(*) FROM failed_logins f 
                        WHERE f.username = v.username 
                        AND DATE(f.timestamp) = DATE(v.timestamp)
                    ), 0) as failed_count
                FROM verified_logins v
                GROUP BY v.username, DATE(v.timestamp)
            """
            )

            conn.commit()
            print(f"[DB] Login statistics aggregated successfully")
            return True

        except Exception as e:
            print(f"[DB ERROR] Failed to aggregate statistics: {e}")
            return False
        finally:
            conn.close()
