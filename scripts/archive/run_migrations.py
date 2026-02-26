"""Run Flask-Migrate (Alembic) upgrades programmatically using the app factory."""

from flask_migrate import upgrade

from app import create_app

app = create_app("development")

with app.app_context():
    print("[MIGRATION] Applying Alembic migrations...")
    upgrade()
    print("[MIGRATION] Done.")
