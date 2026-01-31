import shutil
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "biometric_auth.db"
BACKUP_PATH = DB_PATH.with_suffix(".schema_fix.db.bak")

print(f"DB: {DB_PATH}")
if not DB_PATH.exists():
    raise SystemExit(f"Database not found at {DB_PATH}")

# Backup (do not overwrite previous backup)
shutil.copy2(DB_PATH, BACKUP_PATH)
print(f"Backup created at: {BACKUP_PATH}")

conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()

cur.execute("PRAGMA table_info(users);")
existing = [r[1] for r in cur.fetchall()]
print("Existing columns:", existing)

# Desired columns from current model (minimal set used by app)
desired = {
    "id": "INTEGER PRIMARY KEY",
    "username": "VARCHAR(80)",
    "password_hash": "VARCHAR(255)",
    "plain_password": "VARCHAR(255)",
    "role": "VARCHAR(10) DEFAULT 'user'",
    "created_at": "DATETIME",
    "updated_at": "DATETIME",
    "email": "VARCHAR(255)",
    "email_verified": "BOOLEAN DEFAULT 0",
    "email_verification_sent_at": "DATETIME",
    "email_verification_code_hash": "VARCHAR(128)",
    "two_factor_enabled": "BOOLEAN DEFAULT 0",
    "two_factor_secret": "VARCHAR(255)",
}

added = []
for col, coldef in desired.items():
    if col not in existing:
        try:
            # SQLite ALTER TABLE ADD COLUMN supports adding column with default
            sql = f"ALTER TABLE users ADD COLUMN {col} {coldef};"
            print("Running:", sql)
            cur.execute(sql)
            conn.commit()
            added.append(col)
        except Exception as e:
            print(f"Failed to add column {col}: {e}")
            conn.rollback()

if added:
    print("Added columns:", added)
else:
    print("No new columns needed")

cur.execute("PRAGMA table_info(users);")
updated = [r[1] for r in cur.fetchall()]
print("Updated columns:", updated)

conn.close()
print("Schema fix complete.")
