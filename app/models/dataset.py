"""
Dataset Collection Models

DatasetSubject  — one row per research respondent
DatasetEntry    — one row per keystroke sample

Each subject creates their own password once at registration.
That password is hashed (SHA-256) and stored in DatasetSubject.password_hash.
All subsequent sample submissions are verified against that hash.

Total samples per subject: 100
"""

import json
from datetime import datetime

from . import db

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

DATASET_TOTAL_SAMPLES = 100

# Kept for backward-compat with existing migration files; do not use in new code.
DATASET_SESSIONS         = 1
DATASET_REPS_PER_SESSION = DATASET_TOTAL_SAMPLES


# ─────────────────────────────────────────────────────────────────────────────
# DatasetSubject
# ─────────────────────────────────────────────────────────────────────────────

class DatasetSubject(db.Model):
    """One research respondent.

    subject_code is auto-assigned as 's001', 's002', ... based on creation order.
    name_initial is optional (collected for researcher reference only).
    device_info is auto-detected from the HTTP User-Agent at registration time.
    """

    __tablename__ = "dataset_subjects"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Auto-assigned human-readable code (s001, s002, ...)
    subject_code = db.Column(db.String(10), unique=True, nullable=False, index=True)

    # Optional: name/initial provided by respondent
    name_initial = db.Column(db.String(50), nullable=True)

    # SHA-256 hash of the password the subject chose at registration.
    # All sample submissions are verified against this hash for consistency.
    password_hash = db.Column(db.String(64), nullable=True)

    # Auto-detected from request User-Agent (e.g. "Chrome/Windows", "Safari/macOS")
    device_info = db.Column(db.String(255), nullable=True)

    created_at = db.Column(
        db.DateTime,
        default=datetime.now,
        nullable=False,
    )

    # Relationship to samples
    entries = db.relationship(
        "DatasetEntry",
        back_populates="subject",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"<DatasetSubject {self.subject_code!r}>"

    @classmethod
    def next_subject_code(cls) -> str:
        """Generate the next sequential subject code (e.g. 's042').

        Uses COUNT so the numbering stays consecutive even after rows are
        deleted or the DB is cleared (avoids ID-gap issues with AUTOINCREMENT).
        """
        count = cls.query.count()
        return f"s{count + 1:03d}"

    def total_entries(self) -> int:
        """Total number of keystroke samples collected for this subject."""
        return self.entries.count()

    def completed_sessions(self) -> int:
        """Deprecated — returns 0 or 1 based on completion (no session concept)."""
        return 1 if self.is_complete() else 0

    def is_complete(self) -> bool:
        """True when all required samples have been collected."""
        return self.total_entries() >= DATASET_TOTAL_SAMPLES

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "subject_code": self.subject_code,
            "name_initial": self.name_initial,
            "device_info": self.device_info,
            "created_at": self.created_at.isoformat(),
            "total_entries": self.total_entries(),
            "completed_sessions": self.completed_sessions(),
            "is_complete": self.is_complete(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# DatasetEntry
# ─────────────────────────────────────────────────────────────────────────────

class DatasetEntry(db.Model):
    """One keystroke sample from a respondent.

    Column layout mirrors UsersVector so the same BiometricService utilities
    can process both enrollment vectors and dataset entries without changes.
    """

    __tablename__ = "dataset_entries"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Foreign key to respondent
    subject_id = db.Column(
        db.Integer,
        db.ForeignKey("dataset_subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Global repetition number (1-based, 1 … DATASET_SESSIONS*DATASET_REPS_PER_SESSION).
    # Session and per-session rep are *derived*:
    #   session       = (repetition - 1) // DATASET_REPS_PER_SESSION + 1
    #   rep_in_session = (repetition - 1) % DATASET_REPS_PER_SESSION + 1
    repetition = db.Column(db.Integer, nullable=False)

    # ── Raw timing vectors (JSON arrays) ─────────────────────────────────────
    H_vector  = db.Column(db.Text, nullable=True)   # Hold time
    DD_vector = db.Column(db.Text, nullable=True)   # Down-Down flight
    UD_vector = db.Column(db.Text, nullable=True)   # Up-Down flight
    UU_vector = db.Column(db.Text, nullable=True)   # Up-Up flight
    DU_vector = db.Column(db.Text, nullable=True)   # Down-Up (same as H but diff. agg.)

    # ── Per-vector statistics ─────────────────────────────────────────────────
    H_mean  = db.Column(db.Float, nullable=True)
    H_std   = db.Column(db.Float, nullable=True)
    H_min   = db.Column(db.Float, nullable=True)
    H_max   = db.Column(db.Float, nullable=True)
    H_cv    = db.Column(db.Float, nullable=True)

    DD_mean = db.Column(db.Float, nullable=True)
    DD_std  = db.Column(db.Float, nullable=True)
    DD_min  = db.Column(db.Float, nullable=True)
    DD_max  = db.Column(db.Float, nullable=True)
    DD_cv   = db.Column(db.Float, nullable=True)

    UD_mean = db.Column(db.Float, nullable=True)
    UD_std  = db.Column(db.Float, nullable=True)
    UD_min  = db.Column(db.Float, nullable=True)
    UD_max  = db.Column(db.Float, nullable=True)
    UD_cv   = db.Column(db.Float, nullable=True)

    UU_mean = db.Column(db.Float, nullable=True)
    UU_std  = db.Column(db.Float, nullable=True)
    UU_min  = db.Column(db.Float, nullable=True)
    UU_max  = db.Column(db.Float, nullable=True)
    UU_cv   = db.Column(db.Float, nullable=True)

    DU_mean = db.Column(db.Float, nullable=True)
    DU_std  = db.Column(db.Float, nullable=True)
    DU_min  = db.Column(db.Float, nullable=True)
    DU_max  = db.Column(db.Float, nullable=True)
    DU_cv   = db.Column(db.Float, nullable=True)

    # ── Aggregate timing ──────────────────────────────────────────────────────
    total_duration = db.Column(db.Float, nullable=True)   # seconds
    typing_speed   = db.Column(db.Float, nullable=True)   # chars per second

    created_at = db.Column(
        db.DateTime,
        default=datetime.now,
        nullable=False,
    )

    # Relationship back to subject
    subject = db.relationship("DatasetSubject", back_populates="entries")

    # repetition is a global counter so (subject_id, repetition) is sufficient.
    __table_args__ = (
        db.UniqueConstraint("subject_id", "repetition",
                            name="uq_entry_subject_rep"),
    )

    def __repr__(self) -> str:
        session = (self.repetition - 1) // DATASET_REPS_PER_SESSION + 1
        rep     = (self.repetition - 1) % DATASET_REPS_PER_SESSION + 1
        return (
            f"<DatasetEntry subject={self.subject_id} "
            f"session={session} rep={rep} (global={self.repetition})>"
        )

    # ── Vector helpers (same API as UsersVector) ──────────────────────────────

    def set_vector(self, name: str, values: list) -> None:
        """Serialize a list of floats into the named JSON column."""
        setattr(self, f"{name}_vector", json.dumps(values) if values is not None else None)

    def get_vector(self, name: str) -> list:
        """Deserialize the named JSON column back to a list of floats."""
        raw = getattr(self, f"{name}_vector", None)
        if raw is None:
            return []
        if isinstance(raw, list):
            return raw
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []

    def get_all_vectors(self) -> dict:
        return {name: self.get_vector(name) for name in ("H", "DD", "UD", "UU", "DU")}

    def to_dict(self) -> dict:
        """Full serialisation for API responses and CSV export."""
        session        = (self.repetition - 1) // DATASET_REPS_PER_SESSION + 1
        rep_in_session = (self.repetition - 1) % DATASET_REPS_PER_SESSION + 1
        return {
            "id":            self.id,
            "subject_id":   self.subject_id,
            "repetition":   self.repetition,       # global (1-100)
            "session_no":   session,               # derived
            "rep_in_session": rep_in_session,      # derived
            # vectors
            "H_vector":  self.get_vector("H"),
            "DD_vector": self.get_vector("DD"),
            "UD_vector": self.get_vector("UD"),
            "UU_vector": self.get_vector("UU"),
            "DU_vector": self.get_vector("DU"),
            # stats
            "H_mean":  self.H_mean,  "H_std":  self.H_std,
            "H_min":   self.H_min,   "H_max":  self.H_max,  "H_cv":  self.H_cv,
            "DD_mean": self.DD_mean, "DD_std": self.DD_std,
            "DD_min":  self.DD_min,  "DD_max": self.DD_max, "DD_cv": self.DD_cv,
            "UD_mean": self.UD_mean, "UD_std": self.UD_std,
            "UD_min":  self.UD_min,  "UD_max": self.UD_max, "UD_cv": self.UD_cv,
            "UU_mean": self.UU_mean, "UU_std": self.UU_std,
            "UU_min":  self.UU_min,  "UU_max": self.UU_max, "UU_cv": self.UU_cv,
            "DU_mean": self.DU_mean, "DU_std": self.DU_std,
            "DU_min":  self.DU_min,  "DU_max": self.DU_max, "DU_cv": self.DU_cv,
            # aggregate
            "total_duration": self.total_duration,
            "typing_speed":   self.typing_speed,
            "created_at":     self.created_at.isoformat(),
        }
