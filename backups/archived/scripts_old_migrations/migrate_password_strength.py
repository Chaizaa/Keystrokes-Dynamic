"""
Migration Script: Add password_strength column to existing data
Analyzes existing passwords and classifies them as strong/weak
"""

import csv
import json
import os
import sqlite3
from datetime import datetime

from password_strength import calculate_password_strength


def migrate_database():
    """Add password_strength to SQLite database"""
    import os
    from config import basedir, Config

    db_path = os.path.join(basedir, Config.DATABASE_PATH)

    if not os.path.exists(db_path):
        print(f"⚠️ Database not found: {db_path}")
        print(f"   Skipping database migration")
        return

    print(f"🔄 Migrating database: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(user_vectors)")
        columns = [row[1] for row in cursor.fetchall()]

        if "password_strength" in columns:
            print(f"✅ Column 'password_strength' already exists in database")
        else:
            # Add column
            cursor.execute(
                "ALTER TABLE user_vectors ADD COLUMN password_strength TEXT DEFAULT 'unknown'"
            )
            cursor.execute("ALTER TABLE user_vectors ADD COLUMN password_score INTEGER DEFAULT 0")
            cursor.execute("ALTER TABLE user_vectors ADD COLUMN password_details TEXT DEFAULT '{}'")
            conn.commit()
            print(f"✅ Added columns: password_strength, password_score, password_details")

        # Update existing rows from users table (if available)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if cursor.fetchone():
            print(f"\n🔍 Analyzing passwords from 'users' table...")

            cursor.execute("SELECT username, plain_password FROM users")
            users = cursor.fetchall()

            updated = 0
            for username, password in users:
                strength_result = calculate_password_strength(password)

                cursor.execute(
                    """
                    UPDATE user_vectors 
                    SET password_strength = ?,
                        password_score = ?,
                        password_details = ?
                    WHERE username = ?
                """,
                    (
                        strength_result["strength"],
                        strength_result["score"],
                        json.dumps(strength_result["details"]),
                        username,
                    ),
                )
                updated += cursor.rowcount

            conn.commit()
            print(f"✅ Updated {updated} database records with password strength")
        else:
            print(f"⚠️ 'users' table not found. Cannot auto-classify passwords.")
            print(f"   Passwords will be classified on next enrollment.")

    except Exception as e:
        print(f"❌ Database migration error: {e}")
    finally:
        conn.close()


def migrate_csv():
    """Add password_strength to CSV file"""
    csv_path = "biometric_auth.csv"

    if not os.path.exists(csv_path):
        print(f"⚠️ CSV not found: {csv_path}")
        print(f"   Skipping CSV migration")
        return

    print(f"\n🔄 Migrating CSV: {csv_path}")

    # Backup original
    backup_path = f"biometric_auth_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    os.rename(csv_path, backup_path)
    print(f"✅ Backup created: {backup_path}")

    # Read backup
    rows = []
    with open(backup_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames

        # Check if columns already exist
        if "password_strength" in fieldnames:
            print(f"✅ Column 'password_strength' already exists in CSV")
            # Just copy back
            os.rename(backup_path, csv_path)
            return

        # Add new columns to fieldnames
        new_fieldnames = list(fieldnames) + [
            "password_strength",
            "password_score",
            "password_details",
        ]

        # Read all rows
        for row in reader:
            rows.append(row)

    print(f"📊 Found {len(rows)} rows to migrate")

    # Try to get passwords from database
    import os
    from config import basedir, Config

    db_path = os.path.join(basedir, Config.DATABASE_PATH)
    password_map = {}

    if os.path.exists(db_path):
        print(f"🔍 Loading passwords from database...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT username, plain_password FROM users")
            for username, password in cursor.fetchall():
                password_map[username] = password
            print(f"✅ Loaded {len(password_map)} passwords")
        except:
            print(f"⚠️ Could not load passwords from database")
        finally:
            conn.close()

    # Update rows with password strength
    updated = 0
    unknown = 0

    for row in rows:
        username = row.get("username")

        if username in password_map:
            password = password_map[username]
            strength_result = calculate_password_strength(password)

            row["password_strength"] = strength_result["strength"]
            row["password_score"] = strength_result["score"]
            row["password_details"] = json.dumps(strength_result["details"])
            updated += 1
        else:
            row["password_strength"] = "unknown"
            row["password_score"] = "0"
            row["password_details"] = "{}"
            unknown += 1

    # Write updated CSV
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=new_fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ CSV migration complete:")
    print(f"   - Updated with strength: {updated} rows")
    print(f"   - Unknown strength: {unknown} rows")
    print(f"   - New CSV saved: {csv_path}")


def main():
    print(f"{'='*60}")
    print(f"🚀 PASSWORD STRENGTH MIGRATION")
    print(f"{'='*60}")
    print(f"   Working directory: {os.getcwd()}")
    print()

    # Check if we're in webV2 directory
    if not os.path.exists("app.py"):
        print(f"⚠️ Warning: app.py not found in current directory")
        print(f"   Make sure you run this from webV2/ directory")
        response = input(f"   Continue anyway? (y/n): ")
        if response.lower() != "y":
            return

    # Migrate database
    migrate_database()

    # Migrate CSV
    migrate_csv()

    print(f"\n{'='*60}")
    print(f"✅ MIGRATION COMPLETE!")
    print(f"{'='*60}")
    print(f"\nNext steps:")
    print(f"1. Run: python export_datasets.py")
    print(f"2. Check: datasets/strong_passwords.csv")
    print(f"3. Check: datasets/weak_passwords.csv")


if __name__ == "__main__":
    main()
