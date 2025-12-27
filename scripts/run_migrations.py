"""Run Flask-Migrate (Alembic) upgrades programmatically using the app factory."""
from app import create_app
from flask_migrate import upgrade

app = create_app('development')

with app.app_context():
    print('[MIGRATION] Applying Alembic migrations...')
    upgrade()
    print('[MIGRATION] Done.')
