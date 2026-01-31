import sqlite3

from app.models import User, db
from scripts.migrate_user_vectors_to_feature_vectors import migrate


def test_migration_copies_rows(client, db_session):
    # Prepare legacy DB with a user and one user_vectors row
    from app.blueprints.api import db_manager

    conn = sqlite3.connect(db_manager.db_path)
    cur = conn.cursor()
    # Ensure legacy table exists and matches expected legacy schema
    cur.execute("PRAGMA table_info(user_vectors)")
    cols = [r[1] for r in cur.fetchall()]
    expected_cols = [
        "id",
        "username",
        "user_id",
        "event_type",
        "data_type",
        "H_vector",
        "DD_vector",
        "UD_vector",
        "UU_vector",
        "DU_vector",
        "raw_events",
        "is_successful",
        "timestamp",
    ]
    if not cols:
        cur.execute(
            """CREATE TABLE user_vectors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            user_id INTEGER NOT NULL,
            event_type TEXT NOT NULL DEFAULT 'enrollment',
            data_type TEXT,
            H_vector TEXT,
            DD_vector TEXT,
            raw_events TEXT,
            is_successful INTEGER NOT NULL DEFAULT 1,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
        )
    else:
        # If table exists but schema is missing columns, recreate it with the expected schema
        missing = [c for c in expected_cols if c not in cols]
        if missing:
            # create new table, copy existing columns, drop old, rename
            cur.execute(
                """CREATE TABLE user_vectors_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                user_id INTEGER NOT NULL,
                event_type TEXT NOT NULL DEFAULT 'enrollment',
                data_type TEXT,
                H_vector TEXT,
                DD_vector TEXT,
                UD_vector TEXT,
                UU_vector TEXT,
                DU_vector TEXT,
                raw_events TEXT,
                is_successful INTEGER NOT NULL DEFAULT 1,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
            )
            # copy over columns that exist in the old table
            common = [c for c in expected_cols if c in cols]
            if common:
                cols_csv = ",".join(common)
                cur.execute(
                    f"INSERT INTO user_vectors_new ({cols_csv}) SELECT {cols_csv} FROM user_vectors"
                )
            cur.execute("DROP TABLE user_vectors")
            cur.execute("ALTER TABLE user_vectors_new RENAME TO user_vectors")
    # Insert a user and a legacy enrollment row
    user = User(username="migrateuser")
    user.set_password("MigratePass")
    db.session.add(user)
    db.session.commit()

    # Insert with user_id to satisfy current schema constraints
    # Get the SQLAlchemy user id and insert into legacy DB
    uid = user.id
    from datetime import datetime

    ts = datetime.now().isoformat()
    cur.execute(
        "INSERT INTO user_vectors (username, user_id, event_type, data_type, H_vector, DD_vector, UD_vector, UU_vector, DU_vector, raw_events, is_successful, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "migrateuser",
            uid,
            "enrollment",
            "enrollment",
            "[0.1,0.2]",
            "[0.05,0.06]",
            "[]",
            "[]",
            "[]",
            '[{"key":"a"}]',
            1,
            ts,
        ),
    )
    conn.commit()

    migrated = migrate(db_path=db_manager.db_path, dry_run=False)
    assert migrated >= 1

    # Verify new enrollment_vectors table has the row
    from app.models import EnrollmentVector

    ev = (
        db.session.execute(
            db.select(EnrollmentVector).where(EnrollmentVector.username == "migrateuser")
        )
        .scalars()
        .first()
    )
    assert ev is not None
    assert ev.H_vector is not None
    conn.close()
