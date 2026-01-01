"""
Tests that Alembic migrations run successfully and the expected columns exist after upgrade.
"""

import os
import tempfile

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app import create_app


def test_migrations_apply_and_users_columns_exist(tmp_path, monkeypatch):
    # Create a temporary sqlite file
    db_file = tmp_path / "test_migrations.db"
    db_url = f"sqlite:///{db_file}"

    # Prepare a minimal users table to simulate a pre-migration DB state and stamp initial revision
    from sqlalchemy import create_engine, text

    engine = create_engine(db_url)
    # Create a minimal 'users' table that resembles the initial schema
    with engine.connect() as conn:
        conn.execute(
            text(
                """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                plain_password TEXT,
                password_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
            )
        )
        conn.commit()

    # Create app with the temporary DB (after base table is created)
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": db_url,
            "SECRET_KEY": "migrate-test",
        }
    )
    # Run migrations using alembic config, with app context so env.py can access migrate extension
    with app.app_context():
        # Ensure migrations config points to project migrations
        cfg = Config(
            os.path.join(os.path.dirname(__file__), "..", "..", "migrations", "alembic.ini")
        )
        # Ensure script_location is set so Alembic can find migration scripts
        migrations_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "migrations")
        )
        cfg.set_main_option("script_location", migrations_dir)
        cfg.set_main_option("sqlalchemy.url", db_url)

        # Stamp the database to the initial revision so Alembic knows baseline
        command.stamp(cfg, "c63a68a64ec8")

        # Run upgrade to head (applies only subsequent migrations)
        command.upgrade(cfg, "head")

    # Inspect the resulting DB and check columns
    engine = create_engine(db_url)
    inspector = inspect(engine)
    assert "users" in inspector.get_table_names()

    columns = [col["name"] for col in inspector.get_columns("users")]

    for expected in [
        "email",
        "email_verified",
        "email_verification_sent_at",
        "role",
        "two_factor_enabled",
        "two_factor_secret",
    ]:
        assert expected in columns, f"Missing column {expected} after migration"
