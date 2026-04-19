import os
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import basedir, Config

db_path = os.path.join(basedir, Config.DATABASE_PATH)
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

print("=== DATABASE STRUCTURE ===\n")
for table in tables:
    table_name = table[0]
    print(f"TABLE: {table_name}")

    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()

    for col in columns:
        col_id, col_name, col_type, not_null, default, pk = col
        print(f"  - {col_name} ({col_type})")

    # Get row count
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    print(f"  Total rows: {count}\n")

conn.close()
