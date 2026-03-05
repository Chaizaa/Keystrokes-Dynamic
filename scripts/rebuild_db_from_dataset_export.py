"""Rebuild the SQLite database from `data/dataset_export.csv`.

This script is meant to fix schema drift (old .db missing columns) by:
1) deleting (or optionally backing up) the existing SQLite DB file
2) creating a fresh DB with the current SQLAlchemy/Alembic schema
3) importing enrollment samples from dataset_export.csv into `users` + `users_vectors`
4) (optional) training per-user ML models and storing them in `user_ml_models`

Usage (PowerShell / bash):
  python scripts/rebuild_db_from_dataset_export.py

Optional flags:
  --db-path data/biometric_auth.db
  --csv-path data/dataset_export.csv
  --backup            # copy old DB to backups/archived/ before deleting
  --train-models      # train per-user RF models after import

Notes:
- `dataset_export.csv` currently only contains enrollment rows (event_type=enrollment).
- Users created from the CSV will have password_hash=NULL (password check is skipped).
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import sys
from datetime import datetime
from typing import Any, Dict, Iterable, Optional

# Allow running `python scripts/rebuild_db_from_dataset_export.py` where sys.path[0]
# is `scripts/`. We want the repo root on sys.path so `import app` works.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def _abs_path(repo_root: str, p: str) -> str:
    return os.path.abspath(os.path.join(repo_root, p))


def _coerce_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip()
    if s == "" or s.lower() == "none" or s.lower() == "nan":
        return None
    try:
        return float(s)
    except Exception:
        return None


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)


def _backup_then_delete(db_file: str, do_backup: bool) -> None:
    if not os.path.exists(db_file):
        return

    if do_backup:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(os.path.dirname(__file__), "..", "backups", "archived")
        backup_dir = os.path.abspath(backup_dir)
        os.makedirs(backup_dir, exist_ok=True)
        backup_path = os.path.join(backup_dir, f"biometric_auth.{ts}.db")
        shutil.copy2(db_file, backup_path)
        print(f"[backup] Copied old DB to: {backup_path}")

    os.remove(db_file)
    print(f"[delete] Removed old DB: {db_file}")


def _iter_csv_rows(csv_path: str) -> Iterable[Dict[str, str]]:
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Normalize keys (strip whitespace)
            yield {k.strip(): (v if v is not None else "") for k, v in row.items()}


def main() -> int:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    parser = argparse.ArgumentParser(description="Rebuild DB from dataset_export.csv")
    parser.add_argument("--db-path", default=os.environ.get("DATABASE_PATH", "data/biometric_auth.db"))
    parser.add_argument("--csv-path", default="data/dataset_export.csv")
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--train-models", action="store_true")
    args = parser.parse_args()

    db_file = _abs_path(repo_root, args.db_path)
    csv_file = _abs_path(repo_root, args.csv_path)

    if not os.path.exists(csv_file):
        raise SystemExit(f"CSV not found: {csv_file}")

    _ensure_parent_dir(db_file)

    # Delete old DB (optionally backed up)
    _backup_then_delete(db_file, do_backup=bool(args.backup))

    # Build a minimal Flask app (do NOT call create_app).
    # Calling create_app registers blueprints, which imports legacy sqlite3 helpers
    # that can create an old minimal `users` table and break our fresh schema.
    from flask import Flask
    from app.models import UsersVector, User, db

    db_uri = f"sqlite:///{db_file}"
    app = Flask("rebuild_db")
    app.config.update(
        {
            "TESTING": True,
            "RATELIMIT_ENABLED": False,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": db_uri,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        }
    )
    db.init_app(app)

    with app.app_context():
        # Fresh schema from ORM models.
        db.create_all()

        # Import users + vectors
        user_id_by_username: Dict[str, int] = {}

        def get_or_create_user(username: str) -> int:
            username = (username or "").strip()
            if not username:
                raise ValueError("Empty username in CSV")
            if username in user_id_by_username:
                return user_id_by_username[username]

            u = db.session.query(User).filter_by(username=username).first()
            if not u:
                u = User(username=username)
                # password_hash stays NULL (password check is skipped in login route)
                db.session.add(u)
                db.session.flush()  # assign id
                # after_insert populates user_id on commit; not needed for us
            user_id_by_username[username] = int(u.id)
            return int(u.id)

        inserted = 0
        batch: list[UsersVector] = []
        BATCH_SIZE = 1000

        for row in _iter_csv_rows(csv_file):
            username = row.get("name_initial", "").strip()
            uid = get_or_create_user(username)

            ts = (row.get("created_at") or "").strip()
            if not ts:
                ts = datetime.utcnow().isoformat()

            ev = UsersVector(
                user_id=uid,
                username=username,
                event_type=(row.get("event_type") or "enrollment").strip() or "enrollment",
                data_type=(row.get("event_type") or "enrollment").strip() or "enrollment",
                timestamp=ts,
                is_successful=True,
            )

            # Raw vectors (keep as JSON strings)
            for col in ("H_vector", "DD_vector", "UD_vector", "UU_vector", "DU_vector"):
                if col in row and row[col] != "":
                    setattr(ev, col, row[col])

            # Numeric feature columns used by ML
            numeric_cols = [
                "H_mean",
                "H_std",
                "H_min",
                "H_max",
                "H_cv",
                "DD_mean",
                "DD_std",
                "DD_min",
                "DD_max",
                "DD_cv",
                "UD_mean",
                "UD_std",
                "UD_min",
                "UD_max",
                "UD_cv",
                "UU_mean",
                "UU_std",
                "UU_min",
                "UU_max",
                "UU_cv",
                "DU_mean",
                "DU_std",
                "DU_min",
                "DU_max",
                "DU_cv",
                "total_duration",
                "typing_speed",
            ]
            for col in numeric_cols:
                if col in row:
                    setattr(ev, col, _coerce_float(row[col]))

            batch.append(ev)
            inserted += 1

            if len(batch) >= BATCH_SIZE:
                db.session.add_all(batch)
                db.session.commit()
                batch.clear()

        if batch:
            db.session.add_all(batch)
            db.session.commit()

        # Ensure user_id backfill event has executed
        db.session.commit()

        print(f"[import] Users: {db.session.query(User).count()}")
        print(f"[import] Vectors: {db.session.query(UsersVector).count()}")

        if args.train_models:
            # Train per-user models now so login/verify is instant.
            from app.services.ml_model_service import ml_model_service

            usernames = [u.username for u in db.session.query(User).order_by(User.username.asc()).all()]
            ok = 0
            for uname in usernames:
                res = ml_model_service.train_user_model(uname, force=True)
                print(f"[train] {uname}: success={res.success} reason={res.reason} thr={res.threshold}")
                ok += 1 if res.success else 0
            print(f"[train] trained_ok={ok}/{len(usernames)}")

    # Stamp Alembic head so `flask db upgrade` won't try to replay migrations.
    # This repo's migrations are intended to evolve an existing schema; the initial
    # revision does not create tables from scratch.
    try:
        import sqlite3
        from alembic.config import Config as AlembicConfig
        from alembic.script import ScriptDirectory

        alembic_cfg = AlembicConfig(os.path.join(repo_root, "migrations", "alembic.ini"))
        # Ensure script_location resolves correctly when invoked from repo root
        alembic_cfg.set_main_option("script_location", "migrations")
        script = ScriptDirectory.from_config(alembic_cfg)
        head_rev = script.get_current_head()

        con = sqlite3.connect(db_file)
        cur = con.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)")
        cur.execute("DELETE FROM alembic_version")
        cur.execute("INSERT INTO alembic_version (version_num) VALUES (?)", (head_rev,))
        con.commit()
        con.close()
        print(f"[alembic] stamped head: {head_rev}")
    except Exception as e:
        print(f"[alembic] stamp skipped/failed: {e}")

    print(f"Done. Fresh DB created at: {db_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
