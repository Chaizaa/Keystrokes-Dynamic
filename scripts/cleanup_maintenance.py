#!/usr/bin/env python3
"""
CLEANUP & MAINTENANCE SCRIPT
=============================
Script untuk maintenance database unified login system:
1. Cleanup old verified logins (>30 days)
2. Cleanup old failed logins (>7 days)
3. Aggregate login statistics
4. Show database statistics

Usage:
  python cleanup_maintenance.py              # Show stats only
  python cleanup_maintenance.py --cleanup    # Run cleanup
  python cleanup_maintenance.py --aggregate  # Run aggregation
  python cleanup_maintenance.py --all        # Run all maintenance tasks
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import argparse
import sqlite3
from datetime import datetime, timedelta

# Import db_manager
try:
    from db import DatabaseManager

    db_manager = DatabaseManager()
except Exception as e:
    print(f"❌ Error importing db.py: {e}")
    sys.exit(1)


def show_statistics():
    """Display current database statistics"""
    print("=" * 70)
    print("DATABASE STATISTICS")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    try:
        from config import basedir, Config

        db_path = os.path.join(basedir, Config.DATABASE_PATH)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if new tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]

        print("📊 TABLES:")
        print("-" * 70)

        for table in tables:
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]

            # Get table size
            cursor.execute(f"SELECT SUM(length(name)) FROM {table}")
            size = cursor.fetchone()[0] or 0

            print(f"  • {table:<30} {count:>8} rows")

            # Show additional info for key tables
            if table == "verified_logins":
                # Count by username
                cursor.execute(
                    "SELECT username, COUNT(*) as cnt FROM verified_logins GROUP BY username ORDER BY cnt DESC LIMIT 5"
                )
                top_users = cursor.fetchall()
                if top_users:
                    print(f"    └─ Top users:")
                    for user, cnt in top_users:
                        print(f"       • {user}: {cnt} logins")

                # Recent logins
                cursor.execute(
                    "SELECT COUNT(*) FROM verified_logins WHERE timestamp >= datetime('now', '-24 hours')"
                )
                recent_24h = cursor.fetchone()[0]
                print(f"    └─ Last 24h: {recent_24h} logins")

            elif table == "failed_logins":
                # Count by reason
                cursor.execute(
                    "SELECT reason, COUNT(*) as cnt FROM failed_logins GROUP BY reason ORDER BY cnt DESC"
                )
                reasons = cursor.fetchall()
                if reasons:
                    print(f"    └─ Failure reasons:")
                    for reason, cnt in reasons:
                        print(f"       • {reason}: {cnt}")

                # Recent failures
                cursor.execute(
                    "SELECT COUNT(*) FROM failed_logins WHERE timestamp >= datetime('now', '-24 hours')"
                )
                recent_24h = cursor.fetchone()[0]
                print(f"    └─ Last 24h: {recent_24h} failures")

            elif table == "enrollment_vectors":
                # Count by username
                cursor.execute(
                    "SELECT username, COUNT(*) as cnt FROM enrollment_vectors GROUP BY username ORDER BY cnt DESC LIMIT 5"
                )
                top_users = cursor.fetchall()
                if top_users:
                    print(f"    └─ Top enrolled users:")
                    for user, cnt in top_users:
                        print(f"       • {user}: {cnt} samples")

            elif table == "login_statistics":
                # Latest stats
                cursor.execute(
                    "SELECT date, total_attempts, successful_logins, failed_logins FROM login_statistics ORDER BY date DESC LIMIT 3"
                )
                stats = cursor.fetchall()
                if stats:
                    print(f"    └─ Recent daily stats:")
                    for date, total, success, failed in stats:
                        print(f"       • {date}: {success}/{total} success ({failed} failed)")

        print("-" * 70)

        # Database file size
        if os.path.exists(db_path):
            file_size = os.path.getsize(db_path)
            size_mb = file_size / (1024 * 1024)
            print(f"\n💾 Database File Size: {size_mb:.2f} MB")

        conn.close()

    except Exception as e:
        print(f"❌ Error reading statistics: {e}")
        import traceback

        traceback.print_exc()


def cleanup_old_data(verified_days=30, failed_days=7):
    """Cleanup old verified and failed logins"""
    print("\n" + "=" * 70)
    print("CLEANUP OLD DATA")
    print("=" * 70)

    print(f"\n🧹 Cleaning verified logins older than {verified_days} days...")
    try:
        deleted_verified = db_manager.cleanup_old_verified_logins(days=verified_days)
        print(f"   ✅ Deleted {deleted_verified} old verified login records")
    except Exception as e:
        print(f"   ❌ Error cleaning verified logins: {e}")

    print(f"\n🧹 Cleaning failed logins older than {failed_days} days...")
    try:
        deleted_failed = db_manager.cleanup_old_failed_logins(days=failed_days)
        print(f"   ✅ Deleted {deleted_failed} old failed login records")
    except Exception as e:
        print(f"   ❌ Error cleaning failed logins: {e}")

    print("\n✅ Cleanup complete!")


def aggregate_statistics():
    """Aggregate login statistics"""
    print("\n" + "=" * 70)
    print("AGGREGATE STATISTICS")
    print("=" * 70)

    print("\n📊 Aggregating login statistics...")
    try:
        db_manager.aggregate_login_statistics()
        print("   ✅ Statistics aggregated successfully")

        # Show recent stats
        from config import basedir, Config

        db_path = os.path.join(basedir, Config.DATABASE_PATH)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT date, total_attempts, successful_logins, failed_logins, 
                   avg_verification_score, unique_users
            FROM login_statistics 
            ORDER BY date DESC 
            LIMIT 7
        """
        )

        stats = cursor.fetchall()

        if stats:
            print("\n   Last 7 days statistics:")
            print("   " + "-" * 66)
            print("   Date       | Total | Success | Failed | Avg Score | Users")
            print("   " + "-" * 66)
            for row in stats:
                date, total, success, failed, avg_score, users = row
                avg_score_str = f"{avg_score:.4f}" if avg_score else "N/A"
                print(
                    f"   {date} | {total:>5} | {success:>7} | {failed:>6} | {avg_score_str:>9} | {users:>5}"
                )
            print("   " + "-" * 66)

        conn.close()

    except Exception as e:
        print(f"   ❌ Error aggregating statistics: {e}")
        import traceback

        traceback.print_exc()


def run_all_maintenance():
    """Run all maintenance tasks"""
    print("=" * 70)
    print("RUNNING ALL MAINTENANCE TASKS")
    print("=" * 70)

    # 1. Show current stats
    show_statistics()

    # 2. Cleanup old data
    cleanup_old_data()

    # 3. Aggregate statistics
    aggregate_statistics()

    # 4. Show updated stats
    print("\n" + "=" * 70)
    print("UPDATED STATISTICS AFTER MAINTENANCE")
    print("=" * 70)
    show_statistics()

    print("\n✅ All maintenance tasks completed!")


def main():
    parser = argparse.ArgumentParser(
        description="Cleanup and maintenance script for unified login system"
    )

    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Run cleanup (remove old verified and failed logins)",
    )

    parser.add_argument("--aggregate", action="store_true", help="Aggregate login statistics")

    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all maintenance tasks (cleanup + aggregate)",
    )

    parser.add_argument(
        "--verified-days",
        type=int,
        default=30,
        help="Days to keep verified logins (default: 30)",
    )

    parser.add_argument(
        "--failed-days",
        type=int,
        default=7,
        help="Days to keep failed logins (default: 7)",
    )

    args = parser.parse_args()

    if args.all:
        run_all_maintenance()
    elif args.cleanup:
        show_statistics()
        cleanup_old_data(args.verified_days, args.failed_days)
        print("\n" + "=" * 70)
        print("UPDATED STATISTICS")
        print("=" * 70)
        show_statistics()
    elif args.aggregate:
        show_statistics()
        aggregate_statistics()
    else:
        # Default: just show statistics
        show_statistics()
        print("\n💡 TIP: Use --cleanup, --aggregate, or --all to run maintenance tasks")
        print("   Example: python cleanup_maintenance.py --all")


if __name__ == "__main__":
    main()
