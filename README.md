# Keystrokes-Dynamic

Keystrokes-Dynamic is a Flask web application for behavioral biometric authentication using keystroke dynamics.

## Scope of this branch

This branch is intentionally trimmed for public app usage.

Included:
- runtime Flask application
- templates and static assets
- SQLAlchemy models and migrations
- local run configuration
- Docker local run configuration

Excluded from this branch:
- backups
- raw datasets and database dumps
- research notebooks and experiment artifacts
- internal documentation drafts
- local maintenance/testing scripts

If you need the complete internal snapshot, use branch: `archive/full-repo-20260420`.

## Tech stack

- Python 3.12
- Flask
- SQLAlchemy + Flask-Migrate
- scikit-learn (RF/SVM backend support)
- SQLite (default)

## Project layout

- `app/` core Flask app (blueprints, models, services)
- `templates/` HTML templates
- `static/` CSS and JavaScript
- `migrations/` Alembic migrations
- `config.py` configuration
- `run.py` app entrypoint

## Run locally (without Docker)

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create local env file:

```bash
cp .env.example .env
```

4. Run the app:

```bash
python run.py
```

5. Open:

```text
http://127.0.0.1:5000
```

## Run with Docker (recommended for quick trial)

Before first run, create local env file (recommended):

```bash
cp .env.example .env
```

Build and start:

```bash
docker compose up --build
```

App URL:

```text
http://127.0.0.1:5000
```

Stop containers:

```bash
docker compose down
```

Container status and health:

```bash
docker compose ps
```

Developer first-run flow:

- See `DEVELOPER_FIRST_RUN_CHECKLIST.md` for step-by-step setup + validation.

## Important environment variables

- `SECRET_KEY` session signing key
- `DATABASE_TYPE` default `sqlite`
- `DATABASE_PATH` default `data/biometric_auth.db`
- `MIN_ENROLLMENT_SAMPLES` minimum enrollment samples
- `RECOMMENDED_SAMPLES` UI recommendation value
- `ML_BACKEND` `rf` or `svm`

## Notes

- The app creates required tables at startup in normal development mode.
- Keep `.env` private and never commit it.
- SQLite data is persisted in `data/` when using Docker Compose.