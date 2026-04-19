"""Data loading helpers for SVM scripts."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from common import FEATURE_COLUMNS


def load_joined_dataset(db_path: str | Path) -> pd.DataFrame:
    """Load dataset entries joined with subject metadata from SQLite."""
    query = """
    SELECT
        e.id,
        e.subject_id,
        e.repetition,
        e.created_at,
        s.subject_code,
        s.device_info,
        e.H_mean,
        e.H_std,
        e.H_min,
        e.H_max,
        e.H_cv,
        e.DD_mean,
        e.DD_std,
        e.DD_min,
        e.DD_max,
        e.DD_cv,
        e.UD_mean,
        e.UD_std,
        e.UD_min,
        e.UD_max,
        e.UD_cv,
        e.UU_mean,
        e.UU_std,
        e.UU_min,
        e.UU_max,
        e.UU_cv,
        e.DU_mean,
        e.DU_std,
        e.DU_min,
        e.DU_max,
        e.DU_cv,
        e.total_duration,
        e.typing_speed
    FROM dataset_entries e
    JOIN dataset_subjects s ON s.id = e.subject_id
    """

    conn = sqlite3.connect(str(db_path))
    try:
        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()

    for col in FEATURE_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Keep only rows with complete numeric features.
    df = df.dropna(subset=FEATURE_COLUMNS).reset_index(drop=True)
    return df


def select_subjects_by_entry_count(df: pd.DataFrame, required_entries: int, mode: str = "exact") -> pd.DataFrame:
    """Filter subject classes by entry count.

    mode:
    - exact: subject must have exactly required_entries
    - minimum: subject must have at least required_entries
    """
    counts = df["subject_code"].value_counts()
    if mode == "exact":
        subjects = counts[counts == required_entries].index.tolist()
    elif mode == "minimum":
        subjects = counts[counts >= required_entries].index.tolist()
    else:
        raise ValueError("mode must be 'exact' or 'minimum'")

    return df[df["subject_code"].isin(subjects)].copy().reset_index(drop=True)
