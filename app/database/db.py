import sqlite3
import csv
import os
import json

class Database:
    def __init__(self, db_name="data/biometric_auth.db", csv_name="data/biometric_auth.csv"):
        # Ensure data directory exists
        data_dir = os.path.dirname(db_name)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir)
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
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    plain_password TEXT,
                    password_hash TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create failed_logins table if not exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS failed_logins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT,
                    failure_reason TEXT,
                    verification_score REAL,
                    ip_address TEXT,
                    user_agent TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Check if password_hash column exists
            cursor.execute("PRAGMA table_info(users)")
            columns = [row[1] for row in cursor.fetchall()]
            
            # Add password_hash column if missing (for legacy users)
            if 'password_hash' not in columns:
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
        """Menyimpan data vektor biometrik.

        Prefer SQLAlchemy-backed tables (feature_vectors/enrollment_vectors) when possible.
        Falls back to the legacy CSV+SQLite writer when SQLAlchemy cannot be used.
        Returns True on success, False on failure.
        """
        print(f"\n[INFO] Menyimpan data ke: {self.db_path}")
        # Prefer SQLAlchemy models when available and a user can be resolved
        try:
            from app.models import FeatureVector, EnrollmentVector, User, db as sqlalchemy_db
            import json
            # Attempt to resolve user id
            user_id = None
            if data_dict.get('user_id'):
                try:
                    user_id = int(data_dict.get('user_id'))
                except Exception:
                    user_id = None
            if not user_id and data_dict.get('username'):
                try:
                    from sqlalchemy import select
                    row = sqlalchemy_db.session.execute(select(User.id).where(User.username == data_dict.get('username'))).first()
                    if row:
                        user_id = row[0]
                except Exception:
                    user_id = None

            if user_id:
                # Create an EnrollmentVector for enrollment data
                if data_dict.get('data_type') == 'enrollment' or data_dict.get('event_type') == 'enrollment' or data_dict.get('event_type') is None:
                    ev = EnrollmentVector(user_id=user_id, username=data_dict.get('username'), event_type='enrollment')
                else:
                    ev = FeatureVector(user_id=user_id, username=data_dict.get('username'), event_type=data_dict.get('event_type') or data_dict.get('data_type', 'enrollment'))

                # Map common fields
                for vkey in ('H_vector', 'DD_vector', 'UD_vector', 'UU_vector', 'DU_vector'):
                    if vkey in data_dict:
                        try:
                            setattr(ev, vkey, json.dumps(data_dict[vkey]) if not isinstance(data_dict[vkey], str) else data_dict[vkey])
                        except Exception:
                            setattr(ev, vkey, data_dict[vkey])
                if 'raw_events' in data_dict:
                    ev.raw_events = json.dumps(data_dict['raw_events']) if not isinstance(data_dict['raw_events'], str) else data_dict['raw_events']
                if 'quality_label' in data_dict:
                    ev.quality_label = data_dict['quality_label']
                if 'quality_score' in data_dict:
                    try:
                        ev.quality_score = float(data_dict['quality_score'])
                    except Exception:
                        pass
                if 'password' in data_dict:
                    ev.password = data_dict['password']
                if 'password_strength' in data_dict:
                    ev.password_strength = data_dict['password_strength']
                if 'password_score' in data_dict:
                    try:
                        ev.password_score = float(data_dict['password_score'])
                    except Exception:
                        pass

                sqlalchemy_db.session.add(ev)
                sqlalchemy_db.session.commit()
                print("[INFO] Saved via SQLAlchemy Feature/Enrollment table")
                return True
        except Exception as e:
            # If SQLAlchemy isn't available or fails, fall back to legacy path
            print(f"[INFO] SQLAlchemy save path unavailable or failed: {e}")

        # Fallback: CSV + legacy SQLite writer
        try:
            self._save_to_csv(data_dict)
        except Exception as e:
            print(f"[WARNING] CSV save failed: {e}")
        # Return the boolean success status from SQLite writer
        return self._save_to_sqlite(data_dict)

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
        
        # Add timestamp if not present
        if 'timestamp' not in db_data:
            db_data['timestamp'] = None  # Will use CURRENT_TIMESTAMP default
        
        # Add password column if exists in data but not in db_data
        if 'password' not in db_data and 'real_password_string' in data:
            db_data['password'] = data['real_password_string']

        table_name = "user_vectors"

        # 2. Cek Struktur Tabel & Tambah Kolom Otomatis (Schema Migration)
        try:
            # Cek kolom yang ada sekarang
            cursor.execute(f"PRAGMA table_info({table_name})")
            existing_columns = [row[1] for row in cursor.fetchall()]
            
            # Jika tabel belum ada, buat baru dengan struktur lengkap
            if not existing_columns:
                cursor.execute(f"""
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
                """)
                print(f"[MIGRATION] Created {table_name} table with complete structure")
            else:
                # Ensure timestamp column exists
                if 'timestamp' not in existing_columns:
                    cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                    print("[MIGRATION] Added timestamp column to user_vectors")
                
                # Jika tabel sudah ada, cek apakah ada kolom baru yang perlu ditambah
                for key in db_data.keys():
                    if key not in existing_columns and key != 'id':
                        try:
                            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {key} TEXT")
                        except Exception:
                            pass # Abaikan jika gagal alter

            # 3. Ensure required fields like user_id are present when the schema requires them
            if 'user_id' in existing_columns and (db_data.get('user_id') is None):
                # Try to resolve user_id from users table using username if provided
                try:
                    if db_data.get('username'):
                        cursor.execute("SELECT id FROM users WHERE username = ?", (db_data['username'],))
                        row = cursor.fetchone()
                        if row and row[0]:
                            db_data['user_id'] = str(row[0])
                        else:
                            print(f"[DB ERROR] No user_id found for username: {db_data.get('username')}")
                            conn.close()
                            return False
                except Exception as e:
                    print(f"[DB ERROR] resolving user_id: {e}")
                    conn.close()
                    return False

            # 4. Insert Data
            # Handle schema variants: event_type vs data_type
            if 'event_type' in existing_columns and 'event_type' not in db_data:
                db_data['event_type'] = db_data.get('data_type', 'enrollment')
            if 'data_type' in existing_columns and 'data_type' not in db_data:
                db_data['data_type'] = db_data.get('event_type', 'enrollment')

            # Ensure NOT NULL columns have safe defaults
            try:
                cursor.execute(f"PRAGMA table_info({table_name})")
                cols_info = cursor.fetchall()
                notnull_cols = [r[1] for r in cols_info if r[3] == 1]
                for c in notnull_cols:
                    if c not in db_data or db_data.get(c) is None:
                        # sensible defaults for common columns
                        if c == 'is_successful':
                            db_data[c] = '1'
                        elif c in ('event_type', 'data_type'):
                            db_data[c] = db_data.get('data_type', 'enrollment') or 'enrollment'
                        elif c == 'user_id' and db_data.get('username'):
                            # try to resolve again
                            try:
                                cursor.execute("SELECT id FROM users WHERE username = ?", (db_data['username'],))
                                row = cursor.fetchone()
                                if row and row[0]:
                                    db_data[c] = str(row[0])
                                else:
                                    db_data[c] = ''
                            except Exception:
                                db_data[c] = ''
                        else:
                            db_data[c] = ''
            except Exception:
                pass

            try:
                placeholders = ', '.join(['?'] * len(db_data))
                columns = ', '.join(db_data.keys())
                values = list(db_data.values())

                cursor.execute(f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})", values)
                conn.commit()
                print("[SUKSES] SQLite Updated.")
                conn.close()
                return True

            except Exception as e:
                print(f"[ERROR] SQLite Vector: {e}")
                import traceback
                traceback.print_exc()
                # Attempt a minimal insertion with essential columns to be more tolerant for legacy schemas
                try:
                    essential_keys = ['username', 'data_type', 'event_type', 'user_id', 'H_vector', 'DD_vector', 'password', 'timestamp', 'is_successful']
                    minimal = {k: db_data[k] for k in essential_keys if k in db_data}
                    if minimal:
                        placeholders = ', '.join(['?'] * len(minimal))
                        columns = ', '.join(minimal.keys())
                        values = list(minimal.values())
                        cursor.execute(f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})", values)
                        conn.commit()
                        print("[SUKSES] SQLite Updated (minimal insert).")
                        conn.close()
                        return True
                except Exception as e2:
                    print(f"[ERROR] SQLite minimal insert failed: {e2}")
                    import traceback as tb
                    tb.print_exc()
                conn.close()
                return False
        except Exception as e:
            print(f"[ERROR] SQLite Vector (outer): {e}")
            import traceback
            traceback.print_exc()
            try:
                conn.close()
            except Exception:
                pass
            return False
        finally:
            try:
                conn.close()
            except Exception:
                pass


    # =========================================================================
    # FUNGSI GETTER: MENGAMBIL DATA UNTUK VERIFIKASI
    # =========================================================================
    def get_enrollment_samples(self, username):
        """
        Mengambil semua data sampel pendaftaran (HANYA ENROLLMENT!)
        Supports backward compatibility: enrollment_vectors (new) > user_vectors (old)
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row # Agar hasil return berupa Dict
        cursor = conn.cursor()
        try:
            # Try new table first (enrollment_vectors)
            try:
                cursor.execute("""
                    SELECT * FROM enrollment_vectors 
                    WHERE username = ?
                    ORDER BY id DESC
                """, (username,))
                
                rows = cursor.fetchall()
                
                if rows:
                    print(f"[DB] Loaded {len(rows)} samples from enrollment_vectors (new table)")
                    # Parse JSON strings to Python objects
                    parsed_rows = []
                    for row in rows:
                        row_dict = dict(row)
                        # Parse vector columns from JSON strings to lists
                        for key in ['H_vector', 'DD_vector', 'UD_vector', 'UU_vector', 'DU_vector']:
                            if key in row_dict and isinstance(row_dict[key], str):
                                try:
                                    row_dict[key] = json.loads(row_dict[key])
                                except:
                                    row_dict[key] = []
                        # Parse stats columns from JSON strings to dicts
                        for key in ['H_stats', 'DD_stats', 'UD_stats']:
                            if key in row_dict and isinstance(row_dict[key], str):
                                try:
                                    row_dict[key] = json.loads(row_dict[key])
                                except:
                                    row_dict[key] = {}
                        parsed_rows.append(row_dict)
                    return parsed_rows
            except sqlite3.OperationalError as e:
                # Table doesn't exist yet, fallback to old table
                print(f"[DB] enrollment_vectors not found, using user_vectors (old table)")
            
            # Fallback to old table (user_vectors)
            cursor.execute("""
                SELECT * FROM user_vectors 
                WHERE username = ? AND data_type = 'enrollment'
                ORDER BY id DESC
            """, (username,))
            
            rows = cursor.fetchall()
            print(f"[DB] Loaded {len(rows)} samples from user_vectors (old table)")
            
            # Parse JSON strings to Python objects
            parsed_rows = []
            for row in rows:
                row_dict = dict(row)
                # Parse vector columns from JSON strings to lists
                for key in ['H_vector', 'DD_vector', 'UD_vector', 'UU_vector', 'DU_vector']:
                    if key in row_dict and isinstance(row_dict[key], str):
                        try:
                            row_dict[key] = json.loads(row_dict[key])
                        except:
                            row_dict[key] = []
                # Parse stats columns from JSON strings to dicts
                for key in ['H_stats', 'DD_stats', 'UD_stats']:
                    if key in row_dict and isinstance(row_dict[key], str):
                        try:
                            row_dict[key] = json.loads(row_dict[key])
                        except:
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
            cursor.execute("SELECT * FROM user_vectors WHERE username = ? ORDER BY id DESC LIMIT 1", (username,))
            row = cursor.fetchone()
            if row: return dict(row)
            return None
        except Exception as e:
            print(f"[ERROR] Get User: {e}")
            return None
        finally:
            conn.close()
    
    def get_enrollment_count(self, username):
        """
        Get jumlah enrollment samples untuk user
        Supports multiple schema versions:
          - feature_vectors (new): uses user_id and event_type
          - enrollment_vectors (older)
          - user_vectors (legacy): uses data_type
        """
        # Prefer SQLAlchemy EnrollmentVector if available (canonical)
        try:
            from app.models import EnrollmentVector, db as sqlalchemy_db
            try:
                stmt = sqlalchemy_db.select(EnrollmentVector).where(EnrollmentVector.username == username)
                count = sqlalchemy_db.session.execute(sqlalchemy_db.select(sqlalchemy_db.func.count()).select_from(EnrollmentVector).where(EnrollmentVector.username == username)).scalar_one()
                print(f"[DB] Enrollment count from EnrollmentVector: {count}")
                return int(count)
            except Exception:
                # If SQLAlchemy access fails, continue to file DB fallbacks
                pass
        except Exception:
            pass

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # First try feature_vectors (new schema) using user_id
            try:
                # Get user id
                cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
                row = cursor.fetchone()
                user_id = row[0] if row else None
                if user_id is not None:
                    try:
                        cursor.execute(
                            "SELECT COUNT(*) FROM feature_vectors WHERE user_id = ? AND event_type = 'enrollment'",
                            (user_id,)
                        )
                        count = cursor.fetchone()[0]
                        if count > 0:
                            print(f"[DB] Enrollment count from feature_vectors: {count}")
                            return count
                    except sqlite3.OperationalError:
                        # feature_vectors might not exist or columns differ
                        pass
            except sqlite3.OperationalError:
                # users table missing or other issue - continue to next fallback
                pass

            # Try new table first (enrollment_vectors)
            try:
                cursor.execute("""
                    SELECT COUNT(*) FROM enrollment_vectors 
                    WHERE username = ?
                """, (username,))
                count = cursor.fetchone()[0]
                
                if count > 0:
                    print(f"[DB] Enrollment count from enrollment_vectors: {count}")
                    return count
            except sqlite3.OperationalError:
                # Table doesn't exist, fallback to old table
                pass
            
            # Fallback to old table (user_vectors)
            try:
                cursor.execute("""
                    SELECT COUNT(*) FROM user_vectors 
                    WHERE username = ? AND data_type = 'enrollment'
                """, (username,))
                count = cursor.fetchone()[0]
                print(f"[DB] Enrollment count from user_vectors: {count}")
                return count
            except sqlite3.OperationalError:
                # No suitable table found
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
            # Try feature_vectors first (new schema)
            try:
                cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
                row = cursor.fetchone()
                user_id = row[0] if row else None
                if user_id is not None:
                    try:
                        cursor.execute(
                            "SELECT COUNT(*) FROM feature_vectors WHERE user_id = ? AND event_type = 'login'",
                            (user_id,)
                        )
                        count = cursor.fetchone()[0]
                        if count > 0:
                            print(f"[DB] Login count from feature_vectors: {count}")
                            return count
                    except sqlite3.OperationalError:
                        pass
            except sqlite3.OperationalError:
                pass

            # Fallback to legacy user_vectors table
            try:
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM user_vectors 
                    WHERE username = ? AND data_type = 'login'
                """, (username,))
                count = cursor.fetchone()[0]
                return count
            except sqlite3.OperationalError:
                return 0

        except Exception as e:
            print(f"[DB ERROR] Get Login Count: {e}")
            import traceback
            traceback.print_exc()
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
            # Try users table (new schema). Some installations may have removed the dev-only plain_password column
            try:
                cursor.execute("""
                    SELECT username, created_at as last_login, password_hash
                    FROM users
                    WHERE username = ?
                """, (username,))
                row = cursor.fetchone()
                if row:
                    return dict(row)
            except sqlite3.OperationalError:
                # Older/dev schema might not have password_hash; try a simpler select
                try:
                    cursor.execute("""
                        SELECT username, created_at as last_login
                        FROM users
                        WHERE username = ?
                    """, (username,))
                    row = cursor.fetchone()
                    if row:
                        return dict(row)
                except Exception:
                    pass

            # Fallback to user_vectors table (legacy)
            print(f"[DB] User not found in users table, checking user_vectors for {username}")
            cursor.execute("""
                SELECT DISTINCT 
                    username, 
                    MAX(timestamp) as last_login, 
                    password as plain_password
                FROM user_vectors 
                WHERE username = ?
                GROUP BY username
            """, (username,))
            
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
    def save_dev_credentials(self, username, plain_password, password_hash=None):
        """
        [DEV MODE + SECURITY]
        Menyimpan username, password asli (dev), dan password hash (security).
        Hash digunakan untuk pre-verification sebelum collection/verification mode.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # 1. Buat tabel 'users' dengan kolom password_hash
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    plain_password TEXT,
                    password_hash TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 2. Simpan / Update Password (Upsert sederhana)
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            exists = cursor.fetchone()
            
            if exists:
                # Update password kalau user sudah ada
                if password_hash:
                    cursor.execute("UPDATE users SET plain_password = ?, password_hash = ?, created_at = CURRENT_TIMESTAMP WHERE username = ?", 
                                   (plain_password, password_hash, username))
                else:
                    cursor.execute("UPDATE users SET plain_password = ?, created_at = CURRENT_TIMESTAMP WHERE username = ?", 
                                   (plain_password, username))
                print(f"[DEV MODE] Password asli untuk '{username}' diperbarui di tabel 'users'.")
            else:
                # Insert baru
                if password_hash:
                    cursor.execute("INSERT INTO users (username, plain_password, password_hash) VALUES (?, ?, ?)", 
                                   (username, plain_password, password_hash))
                else:
                    cursor.execute("INSERT INTO users (username, plain_password) VALUES (?, ?)", 
                                   (username, plain_password))
                print(f"[DEV MODE] Password asli untuk '{username}' disimpan di tabel 'users'.")
            
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
            cursor.execute("""
                SELECT * FROM enrollment_vectors
                WHERE username = ?
                ORDER BY id DESC
            """, (username,))
            
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
            cursor.execute("""
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
            """)
            
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
            
            placeholders = ', '.join(['?'] * len(values))
            columns_str = ', '.join(columns)
            
            query = f"INSERT INTO verified_logins ({columns_str}) VALUES ({placeholders})"
            cursor.execute(query, values)
            
            conn.commit()
            print(f"[DB] Verified login saved: {login_data.get('username')} at {login_data.get('timestamp')}")
            return True
            
        except Exception as e:
            print(f"[DB ERROR] Failed to save verified login: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            conn.close()
    
    def log_failed_login(self, username, failure_reason, ip_address=None, user_agent=None, verification_score=None):
        """Log failed login attempt (NO keystroke data saved for security)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO failed_logins 
                (username, failure_reason, verification_score, ip_address, user_agent, timestamp)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (username, failure_reason, verification_score, ip_address, user_agent))
            
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
            cursor.execute("""
                SELECT COUNT(*) FROM verified_logins
                WHERE username = ?
            """, (username,))
            
            count = cursor.fetchone()[0]
            
            # If zero, try user_vectors with data_type='login' as fallback
            if count == 0:
                cursor.execute("""
                    SELECT COUNT(*) FROM user_vectors
                    WHERE username = ? AND data_type = 'login'
                """, (username,))
                count = cursor.fetchone()[0]
            
            return count
            
        except Exception as e:
            print(f"[DB ERROR] Get verified login count: {e}")
            return 0
        finally:
            conn.close()
    
    def get_failed_login_count_recent(self, username, minutes=15):
        """Get count of recent failed login attempts (for rate limiting)

        If rate limiting is turned off in the app config, return 0 so tests and
        dev environments are not treated as rate-limited.
        """
        try:
            from flask import current_app
            if current_app and not current_app.config.get('RATELIMIT_ENABLED', True):
                return 0
        except Exception:
            pass

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT COUNT(*) FROM failed_logins
                WHERE username = ? 
                AND timestamp > datetime('now', '-' || ? || ' minutes')
            """, (username, minutes))
            
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
            cursor.execute("""
                DELETE FROM verified_logins
                WHERE timestamp < datetime('now', '-' || ? || ' days')
            """, (days,))
            
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
            cursor.execute("""
                DELETE FROM failed_logins
                WHERE timestamp < datetime('now', '-' || ? || ' days')
            """, (days,))
            
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
            cursor.execute("""
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
            """)
            
            conn.commit()
            print(f"[DB] Login statistics aggregated successfully")
            return True
            
        except Exception as e:
            print(f"[DB ERROR] Failed to aggregate statistics: {e}")
            return False
        finally:
            conn.close()