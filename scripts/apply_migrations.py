"""
Apply Alembic migrations programmatically (uses project's migrations dir and default DB URL)
Usage: python scripts/apply_migrations.py
"""

import os

from alembic import command
from alembic.config import Config

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
migrations_dir = os.path.join(repo_root, "migrations")
from sqlalchemy import create_engine, inspect

# Default DB URL from config
from config import Config as AppConfig

# Build sqlite URL using same path as in config
db_path = (
    os.path.join(repo_root, AppConfig.DATABASE_PATH)
    if hasattr(AppConfig, "DATABASE_PATH")
    else os.path.join(repo_root, "data", "biometric_auth.db")
)
db_url = f"sqlite:///{db_path}"

print("Applying migrations to", db_url)

cfg = Config(os.path.join(migrations_dir, "alembic.ini"))
cfg.set_main_option("script_location", migrations_dir)
# sqlalchemy.url gets set in env.py via app context; include fallback
cfg.set_main_option("sqlalchemy.url", db_url)

from app import create_app

app = create_app("development")

with app.app_context():
    # Run upgrade within the Flask app context so env.py can access migrate extension
    command.upgrade(cfg, "head")

    print("Migrations applied; current users table columns:")
    engine = create_engine(db_url)
    inspector = inspect(engine)
    cols = [c["name"] for c in inspector.get_columns("users")]
    print(cols)
