"""Run Alembic migrations inside the Flask application context.

Usage:
    python scripts/run_migrations_with_app.py [config_name]

`config_name` defaults to "development". This script ensures the
application context is available so `migrations/env.py` can access
`current_app.extensions['migrate']` safely.
"""
import os
import sys

# Ensure project root on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from alembic.config import Config
from alembic import command
import app.models as app_models
from app import create_app


def main():
    config_name = "development"
    if len(sys.argv) > 1:
        config_name = sys.argv[1]

    # Prevent create_app() from calling `db.create_all()` and creating tables
    # before Alembic runs; temporarily monkeypatch it to a no-op.
    original_create_all = getattr(app_models.db, "create_all", None)
    try:
        app_models.db.create_all = lambda *a, **k: None
        app = create_app(config_name)
    finally:
        # Restore original function (if present)
        if original_create_all is not None:
            app_models.db.create_all = original_create_all
        else:
            try:
                delattr(app_models.db, "create_all")
            except Exception:
                pass

    # Build Alembic config and point it at our migrations dir and DB URL
    migrations_ini = os.path.join(os.path.dirname(__file__), "..", "migrations", "alembic.ini")
    cfg = Config(os.path.abspath(migrations_ini))
    cfg.set_main_option("sqlalchemy.url", app.config.get("SQLALCHEMY_DATABASE_URI") or "")
    cfg.set_main_option("script_location", "migrations")

    with app.app_context():
        from sqlalchemy import inspect

        print(f"Running Alembic migration helper using config '{migrations_ini}' and app config '{config_name}'")

        inspector = inspect(app_models.db.engine)
        existing = set(inspector.get_table_names())
        core_tables = {"users", "user_vectors", "alembic_version"}

        if existing & core_tables:
            # If core tables already exist (likely created by models/db.create_all),
            # it's often safer to stamp the DB as up-to-date instead of attempting
            # to apply the auto-generated initial migration which may assume a
            # different baseline and produce circular dependency errors.
            print("Detected existing core tables in database:", sorted(existing & core_tables))
            print("Stamping the database to the latest revision (marking migrations as applied).")
            command.stamp(cfg, "head")
            print("Database stamped to head. No schema changes applied.")
        else:
            print("No existing core tables found — running Alembic upgrade to head.")
            command.upgrade(cfg, "head")
            print("Migrations applied successfully.")


if __name__ == "__main__":
    main()
