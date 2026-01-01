#!/usr/bin/env python3
import sqlite3
import sys
from pathlib import Path

if len(sys.argv) < 2:
    print("Usage: python scripts/check_user_enrollment.py <email-or-username>")
    sys.exit(1)

identifier = sys.argv[1].strip()
base = Path(__file__).resolve().parents[1]
db_path = base / "data" / "biometric_auth.db"
if not db_path.exists():
    print(f"Database not found at {db_path}")
    sys.exit(1)

con = sqlite3.connect(str(db_path))
cur = con.cursor()

# Try find by email first
cur.execute(
    "SELECT id, username, email, email_verified FROM users WHERE email = ?",
    (identifier,),
)
rows = cur.fetchall()
if rows:
    print("Found user by email:")
    for r in rows:
        print(r)
    uid, username = rows[0][0], rows[0][1]
else:
    # Try find by username
    cur.execute(
        "SELECT id, username, email, email_verified FROM users WHERE username = ?",
        (identifier,),
    )
    rows = cur.fetchall()
    if rows:
        print("Found user by username:")
        for r in rows:
            print(r)
        uid, username = rows[0][0], rows[0][1]
    else:
        print("User not found (by email or username).")
        con.close()
        sys.exit(0)

# Count enrollment samples in user_vectors
cur.execute(
    "SELECT COUNT(*) FROM user_vectors WHERE username = ? AND event_type = 'enrollment'",
    (username,),
)
enroll_count = cur.fetchone()[0]
print(f"Enrollment samples for '{username}': {enroll_count}")

# Show last 5 enrollment rows
cur.execute(
    "SELECT id, timestamp, H_vector IS NOT NULL as has_H, DD_vector IS NOT NULL as has_DD FROM user_vectors WHERE username = ? AND event_type = 'enrollment' ORDER BY id DESC LIMIT 5",
    (username,),
)
rows = cur.fetchall()
print("Last enrollment rows (id, timestamp, has_H, has_DD):")
for r in rows:
    print(r)

con.close()
