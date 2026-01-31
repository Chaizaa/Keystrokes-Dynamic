"""Quick check of current database data"""

import sqlite3
import os
from config import basedir, Config

db_path = os.path.join(basedir, Config.DATABASE_PATH)
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== DATABASE STATUS ===\n")

# Check Users
cursor.execute("SELECT COUNT(*) FROM users")
print(f"Users: {cursor.fetchone()[0]}")

cursor.execute("SELECT * FROM users LIMIT 3")
users = cursor.fetchall()
for u in users:
    print(f"  - {u[1]} (ID: {u[0]})")

# Check user_vectors
try:
    cursor.execute("SELECT COUNT(*) FROM user_vectors")
    print(f"\nKeystroke Vectors: {cursor.fetchone()[0]}")

    cursor.execute(
        "SELECT username, event_type, COUNT(*) FROM user_vectors GROUP BY username, event_type"
    )
    for row in cursor.fetchall():
        print(f"  - {row[0]}: {row[1]} ({row[2]} samples)")
except:
    print("\nKeystroke Vectors: Table not found")

# Check login_attempts
try:
    cursor.execute("SELECT COUNT(*) FROM login_attempts")
    print(f"\nLogin Attempts: {cursor.fetchone()[0]}")
except:
    print("\nLogin Attempts: Table not found")

conn.close()
