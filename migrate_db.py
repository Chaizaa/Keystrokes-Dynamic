import os
import sqlite3
from config import basedir, Config

# Resolve database path from config and ensure data directory exists
db_path = os.path.join(basedir, Config.DATABASE_PATH)
data_dir = os.path.dirname(db_path)
if data_dir and not os.path.exists(data_dir):
    os.makedirs(data_dir, exist_ok=True)
    print(f"Created data directory: {data_dir}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Check if timestamp column exists
    cursor.execute("PRAGMA table_info(user_vectors)")
    columns = [row[1] for row in cursor.fetchall()]

    if "timestamp" not in columns:
        print("Adding timestamp column to user_vectors...")
        # Add column without DEFAULT CURRENT_TIMESTAMP (not allowed in ALTER TABLE)
        cursor.execute("ALTER TABLE user_vectors ADD COLUMN timestamp TEXT")
        conn.commit()
        print("✅ timestamp column added successfully!")
    else:
        print("ℹ️  timestamp column already exists")

    # Also check password column
    if "password" not in columns:
        print("Adding password column to user_vectors...")
        cursor.execute("ALTER TABLE user_vectors ADD COLUMN password TEXT")
        conn.commit()
        print("✅ password column added successfully!")
    else:
        print("ℹ️  password column already exists")

except Exception as e:
    print(f"❌ Error: {e}")
finally:
    conn.close()
