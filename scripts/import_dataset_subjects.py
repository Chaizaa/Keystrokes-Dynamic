"""Import dataset subject samples into users_vectors as enrollment impostor pool.

Example:
    python scripts/import_dataset_subjects.py C:\\Users\\Aiza\\Downloads\\dataset_entries.csv --samples-per-subject 10
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from app.models import UsersVector, db


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


def import_dataset(csv_path: Path, samples_per_subject: int, replace_existing: bool = True) -> dict:
    selected, skipped = _load_selected_rows(csv_path, samples_per_subject)
    app = create_app()

    with app.app_context():
        deleted = 0
        if replace_existing:
            deleted = (
                UsersVector.query
                .filter(UsersVector.username.like(f"{USERNAME_PREFIX}%"))
                .filter(UsersVector.event_type == "enrollment")
                .delete(synchronize_session=False)
            )

        inserted = 0
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
            inserted += 1

        db.session.commit()

    return {
        "deleted_existing": deleted,
        "inserted": inserted,
        "subjects_imported": len({row["subject_id"] for row in selected}),
        "samples_per_subject": samples_per_subject,
        "skipped_subjects": skipped,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import dataset_entries.csv into users_vectors as dataset_subject_* enrollment samples."
    )
    parser.add_argument("csv_path", type=Path, help="Path to dataset_entries.csv")
    parser.add_argument("--samples-per-subject", type=int, default=10)
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append rows instead of replacing existing dataset_subject_* enrollment rows.",
    )
    args = parser.parse_args()

    result = import_dataset(
        csv_path=args.csv_path,
        samples_per_subject=args.samples_per_subject,
        replace_existing=not args.append,
    )

    print(f"deleted_existing={result['deleted_existing']}")
    print(f"inserted={result['inserted']}")
    print(f"subjects_imported={result['subjects_imported']}")
    print(f"samples_per_subject={result['samples_per_subject']}")
    print(
        "skipped_subjects="
        + ",".join(f"{key}:{value}" for key, value in result["skipped_subjects"].items())
    )


if __name__ == "__main__":
    main()
