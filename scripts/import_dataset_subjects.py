"""Import dataset subject samples into users_vectors, and optionally train per-subject models.

The CSV (``dataset_entries.csv``) holds one row per keystroke repetition, grouped by
``subject_id``. Imported rows become ``dataset_subject_<id>`` **enrollment** samples in
``users_vectors``. Those samples serve two purposes:

1. **Impostor pool** — when a real user's SVM/RF model trains, every subject that has at
   least ``MIN_REQUIRED_ENROLLMENT_ROWS`` samples is used as a negative (impostor) class,
   so the classifier learns against real humans instead of only synthetic noise.
2. **Trainable targets** — with ``--train`` the script also trains a model for each subject
   (that subject = genuine, all other subjects = impostors) and reports EER / threshold, so
   you can confirm the SVM actually trains on this dataset end-to-end.

Because ``svm.py`` / ``RF.py`` require a ``users`` row for the *target* username, ``--train``
creates a login-disabled placeholder ``User`` per subject (random unusable password).

Examples
--------
    # import only (build the impostor pool)
    python scripts/import_dataset_subjects.py dataset_entries.csv

    # import + train an SVM model for EVERY subject and print EER
    python scripts/import_dataset_subjects.py dataset_entries.csv --train

    # import + train just subject 1 with the RF backend
    python scripts/import_dataset_subjects.py dataset_entries.csv --train-subject 1 --backend rf
"""

from __future__ import annotations

import argparse
import csv
import secrets
import sys
from collections import defaultdict
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import select

from app import create_app
from app.models import User, UsersVector, db


USERNAME_PREFIX = "dataset_subject_"

FEATURE_COLUMNS = [
    "H_mean", "H_std", "H_min", "H_max", "H_cv",
    "DD_mean", "DD_std", "DD_min", "DD_max", "DD_cv",
    "UD_mean", "UD_std", "UD_min", "UD_max", "UD_cv",
    "UU_mean", "UU_std", "UU_min", "UU_max", "UU_cv",
    "DU_mean", "DU_std", "DU_min", "DU_max", "DU_cv",
    "total_duration", "typing_speed",
]

VECTOR_COLUMNS = ["H_vector", "DD_vector", "UD_vector", "UU_vector", "DU_vector"]


def _to_float(value: str | None) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    return float(value)


def _load_selected_rows(csv_path: Path, samples_per_subject: int) -> tuple[list[dict], dict[str, int]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            subject_id = str(row["subject_id"]).strip()
            grouped[subject_id].append(row)

    selected: list[dict] = []
    skipped: dict[str, int] = {}
    for subject_id, rows in sorted(grouped.items(), key=lambda item: int(item[0])):
        rows = sorted(rows, key=lambda row: int(row.get("repetition") or 0))
        if len(rows) < samples_per_subject:
            skipped[subject_id] = len(rows)
            continue
        selected.extend(rows[:samples_per_subject])
    return selected, skipped


# ---------------------------------------------------------------------------
# DB work (assumes an active Flask app context)
# ---------------------------------------------------------------------------
def _insert_samples(selected: list[dict], replace_existing: bool) -> int:
    deleted = 0
    if replace_existing:
        deleted = (
            UsersVector.query
            .filter(UsersVector.username.like(f"{USERNAME_PREFIX}%"))
            .filter(UsersVector.event_type == "enrollment")
            .delete(synchronize_session=False)
        )

    for row in selected:
        vector = UsersVector(
            username=f"{USERNAME_PREFIX}{str(row['subject_id']).strip()}",
            user_id=None,
            event_type="enrollment",
            timestamp=row.get("created_at") or None,
            is_successful=True,
        )
        for column in VECTOR_COLUMNS:
            setattr(vector, column, row.get(column) or "[]")
        for column in FEATURE_COLUMNS:
            setattr(vector, column, _to_float(row.get(column)))
        db.session.add(vector)

    db.session.commit()
    return deleted


def _model_service(backend: str):
    """Return the concrete model service for the requested backend."""
    if backend == "svm":
        from app.services.svm import svm_model_service
        return svm_model_service
    from app.services.RF import ml_model_service
    return ml_model_service


def _ensure_subject_user(username: str) -> None:
    """Create a login-disabled placeholder ``User`` for a subject if missing.

    ``svm.py`` / ``RF.py`` look up a ``users`` row for the training target, so a
    subject can only be trained as a genuine target when such a row exists. These
    placeholders are research-only: they get a random, unusable password so they
    can never be used to log in.
    """
    existing = db.session.execute(
        select(User).where(User.username == username)
    ).scalars().first()
    if existing:
        return
    user = User()
    user.username = username
    user.email = None
    user.set_password(secrets.token_hex(32))
    db.session.add(user)


def train_subjects(subject_ids: list[str], backend: str, force: bool = True) -> list[dict]:
    """Train a per-subject model for each id; return a list of result dicts."""
    service = _model_service(backend)

    for sid in subject_ids:
        _ensure_subject_user(f"{USERNAME_PREFIX}{sid}")
    db.session.commit()

    results: list[dict] = []
    for sid in subject_ids:
        username = f"{USERNAME_PREFIX}{sid}"
        res = service.train_user_model(username, force=force)
        results.append({
            "subject_id": sid,
            "backend": backend,
            "success": bool(res.success),
            "eer": res.eer,
            "threshold": res.threshold,
            "reason": res.reason,
            "message": res.message,
        })
    return results


def import_dataset(
    csv_path: Path,
    samples_per_subject: int,
    replace_existing: bool = True,
    train: bool = False,
    backend: str = "svm",
    only_subject: str | None = None,
    force: bool = True,
) -> dict:
    selected, skipped = _load_selected_rows(csv_path, samples_per_subject)
    imported_subjects = sorted({str(r["subject_id"]).strip() for r in selected}, key=int)
    app = create_app()

    training_results: list[dict] = []
    with app.app_context():
        deleted = _insert_samples(selected, replace_existing)
        inserted = len(selected)

        do_train = train or only_subject is not None
        if do_train:
            if only_subject is not None:
                only_subject = str(only_subject).strip()
                if only_subject not in imported_subjects:
                    raise SystemExit(
                        f"--train-subject {only_subject} was not imported "
                        f"(available: {', '.join(imported_subjects)})"
                    )
                targets = [only_subject]
            else:
                targets = imported_subjects
            training_results = train_subjects(targets, backend=backend, force=force)

    return {
        "deleted_existing": deleted,
        "inserted": inserted,
        "subjects_imported": len(imported_subjects),
        "samples_per_subject": samples_per_subject,
        "skipped_subjects": skipped,
        "training": training_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import dataset_entries.csv into users_vectors as dataset_subject_* "
                    "enrollment samples, and optionally train per-subject SVM/RF models."
    )
    parser.add_argument("csv_path", type=Path, help="Path to dataset_entries.csv")
    parser.add_argument("--samples-per-subject", type=int, default=10)
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append rows instead of replacing existing dataset_subject_* enrollment rows.",
    )
    parser.add_argument(
        "--train",
        action="store_true",
        help="After import, train a model for every imported subject and print EER/threshold.",
    )
    parser.add_argument(
        "--train-subject",
        type=str,
        default=None,
        metavar="SUBJECT_ID",
        help="Train only this subject id (implies --train).",
    )
    parser.add_argument(
        "--backend",
        choices=["svm", "rf"],
        default="svm",
        help="Model backend to train (default: svm).",
    )
    parser.add_argument(
        "--no-force",
        action="store_true",
        help="Do not retrain a subject that already has a model.",
    )
    args = parser.parse_args()

    result = import_dataset(
        csv_path=args.csv_path,
        samples_per_subject=args.samples_per_subject,
        replace_existing=not args.append,
        train=args.train,
        backend=args.backend,
        only_subject=args.train_subject,
        force=not args.no_force,
    )

    print(f"deleted_existing={result['deleted_existing']}")
    print(f"inserted={result['inserted']}")
    print(f"subjects_imported={result['subjects_imported']}")
    print(f"samples_per_subject={result['samples_per_subject']}")
    print(
        "skipped_subjects="
        + ",".join(f"{key}:{value}" for key, value in result["skipped_subjects"].items())
    )

    if result["training"]:
        print("\n--- training results ---")
        ok = 0
        for r in result["training"]:
            if r["success"]:
                ok += 1
                eer = f"{r['eer']:.4f}" if r["eer"] is not None else "n/a"
                thr = f"{r['threshold']:.4f}" if r["threshold"] is not None else "n/a"
                print(f"  {USERNAME_PREFIX}{r['subject_id']:<3} [{r['backend']}] "
                      f"OK   EER={eer} threshold={thr}")
            else:
                print(f"  {USERNAME_PREFIX}{r['subject_id']:<3} [{r['backend']}] "
                      f"FAIL reason={r['reason']} msg={r['message']}")
        print(f"trained_ok={ok}/{len(result['training'])}")


if __name__ == "__main__":
    main()
