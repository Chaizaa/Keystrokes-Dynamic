"""Migration utility to copy rows from legacy `user_vectors` into the new
`enrollment_vectors`/`feature_vectors` SQLAlchemy tables.

This script can be run as a script or imported (call `migrate()` in tests).
"""

import json
import sqlite3

from app.models import EnrollmentVector, FeatureVector, User, db

DB_PATH = "data/biometric_auth.db"


def migrate(db_path=DB_PATH, limit=None, dry_run=False):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT id, username, event_type, H_vector, DD_vector, UD_vector, UU_vector, DU_vector, raw_events, timestamp FROM user_vectors WHERE event_type = 'enrollment' ORDER BY id ASC"
        )
        rows = cursor.fetchall()
    except Exception as e:
        print(f"[MIGRATE] No legacy user_vectors/enrollment rows found or error: {e}")
        conn.close()
        return 0

    migrated = 0
    for r in rows:
        if limit and migrated >= limit:
            break
        legacy_id, username, event_type, H, DD, UD, UU, DU, raw_events, timestamp = r

        # resolve user
        user_row = (
            db.session.execute(db.select(User).where(User.username == username)).scalars().first()
        )
        if not user_row:
            print(f"[MIGRATE] No user found for username={username}, skipping row {legacy_id}")
            continue

        ev = EnrollmentVector(user_id=user_row.id, username=username, event_type="enrollment")
        if H:
            try:
                ev.H_vector = H if isinstance(H, str) else json.dumps(H)
            except Exception:
                ev.H_vector = str(H)
        if DD:
            try:
                ev.DD_vector = DD if isinstance(DD, str) else json.dumps(DD)
            except Exception:
                ev.DD_vector = str(DD)
        if raw_events:
            ev.raw_events = raw_events if isinstance(raw_events, str) else json.dumps(raw_events)

        if not dry_run:
            db.session.add(ev)
            db.session.commit()
            migrated += 1
            print(f"[MIGRATE] Migrated legacy id {legacy_id} -> enrollment id {ev.id}")

    conn.close()
    print(f"[MIGRATE] Done. Migrated {migrated} rows.")
    return migrated


if __name__ == "__main__":
    migrate()
