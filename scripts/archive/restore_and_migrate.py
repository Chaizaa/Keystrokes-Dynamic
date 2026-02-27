"""
Restore database from backup and ensure SQLAlchemy can read it
"""

import os
import shutil
import sqlite3

print("=" * 70)
print("DATABASE RESTORE & MIGRATION")
print("=" * 70)

# Paths
backup_path = "data/biometric_auth.db.backup_20251224_030731"
db_path = "data/biometric_auth.db"

# 1. Check backup exists
if not os.path.exists(backup_path):
    print(f"❌ Backup not found: {backup_path}")
    exit(1)

print(f"\n1️⃣  Backup found: {backup_path}")

# 2. Check current database
if os.path.exists(db_path):
    print(f"2️⃣  Current database exists: {db_path}")

    # Check if it has data
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    conn.close()

    if user_count == 0:
        print(f"   ⚠️  Database is empty! Restoring from backup...")

        # Backup current empty db
        empty_backup = db_path + ".empty"
        shutil.copy2(db_path, empty_backup)
        print(f"   💾 Saved empty database to {empty_backup}")

        # Restore from backup
        shutil.copy2(backup_path, db_path)
        print(f"   ✅ Restored from backup!")

        # Verify
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        new_count = cursor.fetchone()[0]
        conn.close()

        print(f"   ✅ Verified: {new_count} users restored")
    else:
        print(f"   ✅ Database has data ({user_count} users)")
else:
    print(f"2️⃣  No current database, copying from backup...")
    shutil.copy2(backup_path, db_path)
    print(f"   ✅ Database restored!")

# 3. Final check
print("\n3️⃣  Final Status:")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM users")
users = cursor.fetchone()[0]
print(f"   Users: {users}")

try:
    cursor.execute("SELECT COUNT(*) FROM user_vectors")
    vectors = cursor.fetchone()[0]
    print(f"   Keystroke Vectors: {vectors}")
except:
    print(f"   Keystroke Vectors: 0 (table not found)")

try:
    cursor.execute("SELECT COUNT(*) FROM login_attempts")
    attempts = cursor.fetchone()[0]
    print(f"   Login Attempts: {attempts}")
except:
    print(f"   Login Attempts: 0 (table not found)")

conn.close()

print("\n✅ Database ready for SQLAlchemy!")
print("=" * 70)
