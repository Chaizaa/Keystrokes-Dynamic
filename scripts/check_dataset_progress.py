"""
Real-time Dataset Collection Monitor
Usage: python check_dataset_progress.py
"""

import os
import sqlite3
from datetime import datetime

import pandas as pd


def get_db_stats():
    """Get stats from SQLite database"""
    import os
    from config import basedir, Config

    db_path = os.path.join(basedir, Config.DATABASE_PATH)

    if not os.path.exists(db_path):
        return None

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Total samples
        cursor.execute("SELECT COUNT(*) FROM user_vectors")
        total = cursor.fetchone()[0]

        # Total users
        cursor.execute("SELECT COUNT(DISTINCT username) FROM user_vectors")
        users = cursor.fetchone()[0]

        # Enrollment vs Login
        cursor.execute("SELECT COUNT(*) FROM user_vectors WHERE data_type = 'enrollment'")
        enrollment = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM user_vectors WHERE data_type = 'login'")
        login = cursor.fetchone()[0]

        # Per-user breakdown
        cursor.execute(
            """
            SELECT username, data_type, COUNT(*) 
            FROM user_vectors 
            GROUP BY username, data_type
            ORDER BY username
        """
        )
        user_breakdown = {}
        for row in cursor.fetchall():
            username, dtype, count = row
            if username not in user_breakdown:
                user_breakdown[username] = {"enrollment": 0, "login": 0}
            user_breakdown[username][dtype] = count

        conn.close()

        return {
            "total": total,
            "users": users,
            "enrollment": enrollment,
            "login": login,
            "breakdown": user_breakdown,
        }
    except Exception as e:
        print(f"Error reading database: {e}")
        return None


def monitor_progress():
    stats = get_db_stats()

    if not stats:
        print("❌ Database tidak ditemukan atau kosong!")
        print("   Mulai collection dengan: python app.py")
        print("   Lalu buka: http://127.0.0.1:5000/register")
        return

    print("=" * 80)
    print(" 📊 DATASET COLLECTION PROGRESS")
    print("=" * 80)
    print(f" Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Overall stats
    total_samples = stats["total"]
    total_users = stats["users"]
    enrollment = stats["enrollment"]
    login = stats["login"]

    print(f"📦 TOTAL SAMPLES: {total_samples}")
    print(f"👥 TOTAL USERS: {total_users}")
    print(f"   ├─ Enrollment: {enrollment} samples")
    print(f"   └─ Login: {login} samples")
    print()

    # Target progress
    target = 3000
    progress_pct = (total_samples / target) * 100

    bar_length = 50
    filled = int(min(bar_length, bar_length * total_samples / target))
    bar = "█" * filled + "░" * (bar_length - filled)

    print(f"🎯 TARGET PROGRESS: {total_samples}/{target} ({progress_pct:.1f}%)")
    print(f"   [{bar}]")
    print()

    # Daily rate estimation
    if total_users > 0:
        avg_per_user = total_samples / total_users
        remaining = target - total_samples
        users_needed = int(remaining / 20) if remaining > 0 else 0

        print(f"📈 STATISTICS:")
        print(f"   ├─ Avg samples per user: {avg_per_user:.1f}/20")
        print(f"   ├─ Remaining samples: {remaining}")
        print(f"   └─ Users needed: ~{users_needed}")
        print()

    # Per-user breakdown
    print(f"👤 USER PROGRESS (last 15):")
    print("-" * 80)
    print(f"{'Username':<20} {'Enrollment':<12} {'Login':<12} {'Total':<8} Status")
    print("-" * 80)

    breakdown = stats["breakdown"]
    usernames = sorted(breakdown.keys(), reverse=True)[:15]  # Last 15 users

    for username in usernames:
        enr = breakdown[username].get("enrollment", 0)
        log = breakdown[username].get("login", 0)
        total = enr + log

        if total >= 20:
            status = "✅ COMPLETE"
        elif total >= 15:
            status = "🟡 Almost"
        elif total >= 10:
            status = "🟠 Halfway"
        else:
            status = "🔴 Started"

        print(f"{username:<20} {enr:<12} {log:<12} {total:<8} {status}")

    print("=" * 80)

    # Recommendations
    if total_samples < 1000:
        print("\n💡 TIP: Keep recruiting! Target 20-25 users per day")
    elif total_samples < 2000:
        print("\n💡 TIP: Halfway there! Maintain momentum")
    elif total_samples < target:
        print("\n💡 TIP: Almost done! Push for final users")
    else:
        print("\n🎉 TARGET ACHIEVED! Great job!")
        print(f"   You collected {total_samples} samples from {total_users} users")

    print()


if __name__ == "__main__":
    import time

    try:
        while True:
            os.system("cls" if os.name == "nt" else "clear")
            monitor_progress()
            print("🔄 Refreshing in 5 Mins... (Ctrl+C to stop)")
            time.sleep(300)
    except KeyboardInterrupt:
        print("\n\n👋 Monitoring stopped.")
