import shutil
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "biometric_auth.db"
BACKUP_PATH = DB_PATH.with_suffix(".db.bak")

print(f"DB: {DB_PATH}")
if not DB_PATH.exists():
    raise SystemExit(f"Database not found at {DB_PATH}")

# Backup
shutil.copy2(DB_PATH, BACKUP_PATH)
print(f"Backup created at: {BACKUP_PATH}")

conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()

# Check if 'role' column exists
cur.execute("PRAGMA table_info(users);")
cols = [r[1] for r in cur.fetchall()]
print("Existing columns:", cols)

if "role" in cols:
    print("Column 'role' already exists. No changes made.")
else:
    try:
        # Add column with default 'user' and not null
        cur.execute("ALTER TABLE users ADD COLUMN role VARCHAR(10) DEFAULT 'user';")
        conn.commit()
        print("Added 'role' column with default 'user'.")
    except Exception as e:
        print("Failed to add column:", e)
        conn.rollback()

# Re-check
cur.execute("PRAGMA table_info(users);")
cols = [r[1] for r in cur.fetchall()]
print("Updated columns:", cols)

conn.close()
print("Done.")
