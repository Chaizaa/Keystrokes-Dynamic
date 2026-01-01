"""
Database Migration Script: Unified Login Schema
================================================
This script migrates from dual-mode (collection + verification) to unified login.

Creates three separate tables:
1. enrollment_vectors - Pure training data (from registration)
2. verified_logins - Successful login attempts only
3. failed_logins - Security log (no keystroke data)

Usage:
    python migrate_unified_login.py
"""

import json
import os
import sqlite3
from datetime import datetime

from config import basedir, Config

DB_PATH = os.path.join(basedir, Config.DATABASE_PATH)


def backup_database():
    """Create backup of current database"""
    if os.path.exists(DB_PATH):
        backup_path = f"{DB_PATH}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        import shutil

        shutil.copy2(DB_PATH, backup_path)
        print(f"✅ Database backed up to: {backup_path}")
        return backup_path
    return None


def create_new_tables():
    """Create new table structure for unified login"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        print("\n📊 Creating new table structure...")

        # ============================================
        # TABLE 1: enrollment_vectors
        # ============================================
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS enrollment_vectors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                
                -- Timing vectors (JSON)
                H_vector TEXT,
                DD_vector TEXT,
                UD_vector TEXT,
                UU_vector TEXT,
                DU_vector TEXT,
                
                -- Statistical features (JSON)
                statistical_features TEXT,
                
                -- Metadata
                quality_label TEXT,
                quality_score INTEGER,
                password_strength TEXT,
                
                FOREIGN KEY (username) REFERENCES users(username)
            )
        """
        )
        print("  ✓ Created table: enrollment_vectors")

        # ============================================
        # TABLE 2: verified_logins
        # ============================================
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS verified_logins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                
                -- Timing vectors (JSON)
                H_vector TEXT,
                DD_vector TEXT,
                UD_vector TEXT,
                UU_vector TEXT,
                DU_vector TEXT,
                
                -- Verification results
                verification_score REAL,
                recommended_method TEXT,
                consensus_accept INTEGER,
                consensus_total INTEGER,
                all_methods_results TEXT,
                
                -- Metadata
                login_success INTEGER DEFAULT 1,
                ip_address TEXT,
                user_agent TEXT,
                
                FOREIGN KEY (username) REFERENCES users(username)
            )
        """
        )
        print("  ✓ Created table: verified_logins")

        # ============================================
        # TABLE 3: failed_logins
        # ============================================
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS failed_logins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                
                -- Failure reason
                failure_reason TEXT,
                verification_score REAL,
                
                -- Metadata (NO KEYSTROKE DATA for security)
                ip_address TEXT,
                user_agent TEXT
            )
        """
        )
        print("  ✓ Created table: failed_logins")

        # ============================================
        # TABLE 4: login_statistics (for aggregation)
        # ============================================
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS login_statistics (
                username TEXT,
                date TEXT,
                login_count INTEGER,
                avg_score REAL,
                failed_count INTEGER DEFAULT 0,
                PRIMARY KEY (username, date)
            )
        """
        )
        print("  ✓ Created table: login_statistics")

        conn.commit()
        print("✅ All tables created successfully!")

    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        conn.rollback()
    finally:
        conn.close()


def migrate_existing_data():
    """Migrate data from old user_vectors table to new structure"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if old table exists
        cursor.execute(
            """
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='user_vectors'
        """
        )

        if not cursor.fetchone():
            print("\n⚠️  No user_vectors table found. Skipping migration.")
            return

        print("\n🔄 Migrating existing data...")

        # Check if data_type column exists
        cursor.execute("PRAGMA table_info(user_vectors)")
        columns = [row[1] for row in cursor.fetchall()]

        if "data_type" in columns:
            # Migrate enrollment data
            cursor.execute(
                """
                INSERT OR IGNORE INTO enrollment_vectors 
                (username, password_hash, timestamp, H_vector, DD_vector, UD_vector, 
                 UU_vector, DU_vector, statistical_features, quality_label, 
                 quality_score, password_strength)
                SELECT username, password_hash, timestamp, H_vector, DD_vector, 
                       UD_vector, UU_vector, DU_vector, statistical_features, 
                       quality_label, quality_score, password_strength
                FROM user_vectors
                WHERE data_type = 'enrollment'
            """
            )

            enrollment_count = cursor.rowcount
            print(f"  ✓ Migrated {enrollment_count} enrollment records")

            # Note: Login data from old system is NOT migrated
            # (mixed verified/unverified data, better to start fresh)
            print("  ⚠️  Old login data NOT migrated (start fresh for clean data)")

        else:
            # Old schema without data_type, assume all are enrollment
            cursor.execute(
                """
                INSERT OR IGNORE INTO enrollment_vectors 
                (username, password_hash, timestamp, H_vector, DD_vector, UD_vector, 
                 UU_vector, DU_vector, statistical_features, quality_label, 
                 quality_score, password_strength)
                SELECT username, password_hash, timestamp, H_vector, DD_vector, 
                       UD_vector, UU_vector, DU_vector, statistical_features, 
                       quality_label, quality_score, password_strength
                FROM user_vectors
            """
            )

            enrollment_count = cursor.rowcount
            print(f"  ✓ Migrated {enrollment_count} records as enrollment data")

        conn.commit()
        print("✅ Data migration completed!")

    except Exception as e:
        print(f"❌ Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()


def create_indexes():
    """Create indexes for better query performance"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        print("\n🔍 Creating indexes...")

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_enrollment_username 
            ON enrollment_vectors(username)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_verified_username 
            ON verified_logins(username)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_verified_timestamp 
            ON verified_logins(timestamp)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_failed_username 
            ON failed_logins(username)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_failed_timestamp 
            ON failed_logins(timestamp)
        """
        )

        conn.commit()
        print("✅ Indexes created successfully!")

    except Exception as e:
        print(f"❌ Error creating indexes: {e}")
    finally:
        conn.close()


def verify_migration():
    """Verify migration results"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        print("\n📊 Migration Statistics:")
        print("=" * 50)

        # Count enrollment records
        cursor.execute("SELECT COUNT(*) FROM enrollment_vectors")
        enrollment_count = cursor.fetchone()[0]
        print(f"  📚 Enrollment vectors: {enrollment_count}")

        # Count verified logins
        cursor.execute("SELECT COUNT(*) FROM verified_logins")
        verified_count = cursor.fetchone()[0]
        print(f"  ✅ Verified logins: {verified_count}")

        # Count failed logins
        cursor.execute("SELECT COUNT(*) FROM failed_logins")
        failed_count = cursor.fetchone()[0]
        print(f"  ❌ Failed logins: {failed_count}")

        # Count unique users
        cursor.execute("SELECT COUNT(DISTINCT username) FROM enrollment_vectors")
        unique_users = cursor.fetchone()[0]
        print(f"  👥 Unique users: {unique_users}")

        print("=" * 50)

        # Show per-user enrollment counts
        cursor.execute(
            """
            SELECT username, COUNT(*) as count 
            FROM enrollment_vectors 
            GROUP BY username 
            ORDER BY count DESC 
            LIMIT 10
        """
        )

        print("\n🔝 Top Users by Enrollment Count:")
        for row in cursor.fetchall():
            print(f"  • {row[0]}: {row[1]} samples")

    except Exception as e:
        print(f"❌ Error verifying migration: {e}")
    finally:
        conn.close()


def main():
    """Main migration process"""
    print("=" * 60)
    print("🚀 UNIFIED LOGIN MIGRATION")
    print("=" * 60)

    # Step 1: Backup
    backup_path = backup_database()

    # Step 2: Create new tables
    create_new_tables()

    # Step 3: Migrate data
    migrate_existing_data()

    # Step 4: Create indexes
    create_indexes()

    # Step 5: Verify
    verify_migration()

    print("\n" + "=" * 60)
    print("✅ MIGRATION COMPLETED SUCCESSFULLY!")
    print("=" * 60)
    print("\n📝 Next Steps:")
    print("  1. Update app.py with new /api/login endpoint")
    print("  2. Update login.html to remove mode selection")
    print("  3. Test unified login flow")
    print(f"\n💾 Backup saved at: {backup_path}")
    print("\n⚠️  If issues occur, restore from backup:")
    print(f"   cp {backup_path} {DB_PATH}")


if __name__ == "__main__":
    main()
