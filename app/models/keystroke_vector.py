"""
UsersVector Model - Unified biometric keystroke storage for both register and login.

  event_type = 'enrollment'  → samples captured during registration
  event_type = 'login'       → samples captured during login attempt

Schema mirrors biometric_system.db reference exactly.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json

from sqlalchemy import Index, event, select
from sqlalchemy.orm.attributes import set_committed_value

from . import db
from .user import User


class UsersVector(db.Model):
    """
    Unified keystroke biometric storage.
    Used for both enrollment (register) and login verification.

    Timing features:
      H   = Hold Time    (key-down duration)
      DD  = Down-Down    (consecutive key-down intervals)
      UD  = Up-Down      (key-up to next key-down)
      UU  = Up-Up        (consecutive key-up intervals)
      DU  = Down-Up      (key-down to its own key-up = same as H, different aggregate)
    """

    __tablename__ = "users_vectors"

    __table_args__ = (
        Index("idx_vector_user_event_type", "user_id", "event_type"),
        Index("idx_vector_username_event", "username", "event_type"),
        Index("idx_vector_user_timestamp", "user_id", "timestamp"),
    )

    # --- Primary key ---
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # --- Identity (user_id is optional FK for legacy rows without it) ---
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # --- Identity ---
    username = db.Column(db.Text, nullable=True, index=True)
    # Keep TEXT to match existing DBs; ensure it is never NULL.
    timestamp = db.Column(
        db.Text,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).isoformat(),
        index=True,
    )
    password_hash = db.Column(db.Text, nullable=True)

    # --- Legacy compatibility ---
    # Older code/tests used `is_successful` and `data_type`.
    is_successful = db.Column(db.Boolean, nullable=False, default=True)
    data_type = db.Column(db.Text, nullable=True, index=True)

    # --- Aggregate timing ---
    total_duration = db.Column(db.Float, nullable=True)

    # --- Raw timing vectors (JSON arrays) ---
    H_vector  = db.Column(db.Text, nullable=True)
    DD_vector = db.Column(db.Text, nullable=True)
    UD_vector = db.Column(db.Text, nullable=True)
    UU_vector = db.Column(db.Text, nullable=True)
    DU_vector = db.Column(db.Text, nullable=True)

    # --- Per-vector statistics ---
    H_mean  = db.Column(db.Float, nullable=True)
    H_std   = db.Column(db.Float, nullable=True)
    H_min   = db.Column(db.Float, nullable=True)
    H_max   = db.Column(db.Float, nullable=True)

    DD_mean = db.Column(db.Float, nullable=True)
    DD_std  = db.Column(db.Float, nullable=True)
    DD_min  = db.Column(db.Float, nullable=True)
    DD_max  = db.Column(db.Float, nullable=True)

    UD_mean = db.Column(db.Float, nullable=True)
    UD_std  = db.Column(db.Float, nullable=True)
    UD_min  = db.Column(db.Float, nullable=True)
    UD_max  = db.Column(db.Float, nullable=True)

    UU_mean = db.Column(db.Float, nullable=True)
    UU_std  = db.Column(db.Float, nullable=True)
    UU_min  = db.Column(db.Float, nullable=True)
    UU_max  = db.Column(db.Float, nullable=True)

    DU_mean = db.Column(db.Float, nullable=True)
    DU_std  = db.Column(db.Float, nullable=True)
    DU_min  = db.Column(db.Float, nullable=True)
    DU_max  = db.Column(db.Float, nullable=True)

    # --- Typing speed ---
    typing_speed = db.Column(db.Float, nullable=True)

    # --- Coefficient of variation per vector ---
    H_cv  = db.Column(db.Float, nullable=True)
    DD_cv = db.Column(db.Float, nullable=True)
    UD_cv = db.Column(db.Float, nullable=True)
    UU_cv = db.Column(db.Float, nullable=True)
    DU_cv = db.Column(db.Float, nullable=True)

    # --- Flow discriminator ---
    # PRIMARY: Use event_type for all new code
    event_type = db.Column(db.Text, nullable=True, index=True)  # 'enrollment' | 'login'
    # DEPRECATED: data_type kept for backward compatibility, but always read from event_type
    # data_type = db.Column(db.Text, nullable=True, index=True)  # DEPRECATED - use event_type instead

    def __init__(self, **kwargs):
        """Constructor with backward-compatible kwarg aliases.

        Many older scripts/tests used lowercase vector kwargs like `h_vector`.
        The canonical columns are `H_vector`, `DD_vector`, etc.
        """
        # Map legacy kwarg names -> canonical column names
        legacy_map = {
            "h_vector": "H_vector",
            "dd_vector": "DD_vector",
            "ud_vector": "UD_vector",
            "uu_vector": "UU_vector",
            "du_vector": "DU_vector",
        }
        for old, new in legacy_map.items():
            if old in kwargs and new not in kwargs:
                kwargs[new] = kwargs.pop(old)

        # Keep event_type and data_type in sync (best-effort)
        if "event_type" not in kwargs and "data_type" in kwargs:
            kwargs["event_type"] = kwargs.get("data_type")
        if "data_type" not in kwargs and "event_type" in kwargs:
            kwargs["data_type"] = kwargs.get("event_type")

        super().__init__(**kwargs)

    def __repr__(self):
        event = self.event_type or self.data_type or "unknown"
        return f"<UsersVector {self.username!r} [{event}] @ {self.timestamp}>"

    # ---------------------------------------------------------------------
    # Convenience accessors expected by some tests / legacy callers
    # ---------------------------------------------------------------------

    def get_H_vector(self) -> list:
        return self.get_vector("H")

    def get_DD_vector(self) -> list:
        return self.get_vector("DD")

    def get_UD_vector(self) -> list:
        return self.get_vector("UD")

    def get_UU_vector(self) -> list:
        return self.get_vector("UU")

    def get_DU_vector(self) -> list:
        return self.get_vector("DU")

    @property
    def h_vector(self) -> list:
        return self.get_H_vector()

    @h_vector.setter
    def h_vector(self, values) -> None:
        self.set_vector("H", values)

    @property
    def dd_vector(self) -> list:
        return self.get_DD_vector()

    @dd_vector.setter
    def dd_vector(self, values) -> None:
        self.set_vector("DD", values)

    @property
    def ud_vector(self) -> list:
        return self.get_UD_vector()

    @ud_vector.setter
    def ud_vector(self, values) -> None:
        self.set_vector("UD", values)

    @property
    def uu_vector(self) -> list:
        return self.get_UU_vector()

    @uu_vector.setter
    def uu_vector(self, values) -> None:
        self.set_vector("UU", values)

    @property
    def du_vector(self) -> list:
        return self.get_DU_vector()

    @du_vector.setter
    def du_vector(self, values) -> None:
        self.set_vector("DU", values)

    def get_vector(self, name: str) -> list:
        """Parse a named vector column (H/DD/UD/UU/DU) from JSON string.

        Args:
            name: vector name, one of 'H', 'DD', 'UD', 'UU', 'DU'

        Returns:
            list of float values, or empty list if missing/invalid
        """
        raw = getattr(self, f"{name}_vector", None)
        if raw is None:
            return []
        if isinstance(raw, list):
            return raw
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_vector(self, name: str, values: list) -> None:
        """Serialize a list into the named vector column as JSON.

        Args:
            name: vector name, one of 'H', 'DD', 'UD', 'UU', 'DU'
            values: list of float values to store
        """
        setattr(self, f"{name}_vector", json.dumps(values) if values is not None else None)

    def get_all_vectors(self) -> dict:
        """Return all timing vectors as a dict of lists.

        Returns:
            dict with keys H, DD, UD, UU, DU each containing a list of floats
        """
        return {
            name: self.get_vector(name)
            for name in ("H", "DD", "UD", "UU", "DU")
        }

    @property
    def is_enrollment(self) -> bool:
        """True if this sample was captured during registration."""
        return self.event_type == "enrollment"

    @property
    def is_login(self) -> bool:
        """True if this sample was captured during a login attempt."""
        return self.event_type == "login"

    def to_dict(self) -> dict:
        """Full dict representation including all statistics for API responses."""
        ts = self.timestamp
        try:
            if isinstance(ts, datetime):
                ts = ts.isoformat()
        except Exception:
            pass
        return {
            "id": self.id,
            "username": self.username,
            "timestamp": ts,
            "event_type": self.event_type,
            "total_duration": self.total_duration,
            "typing_speed": self.typing_speed,
            # Per-vector statistics
            "H_mean": self.H_mean,   "H_std": self.H_std,
            "H_min": self.H_min,    "H_max": self.H_max,
            "H_cv": self.H_cv,
            "DD_mean": self.DD_mean, "DD_std": self.DD_std,
            "DD_min": self.DD_min,   "DD_max": self.DD_max,
            "DD_cv": self.DD_cv,
            "UD_mean": self.UD_mean, "UD_std": self.UD_std,
            "UD_min": self.UD_min,   "UD_max": self.UD_max,
            "UD_cv": self.UD_cv,
            "UU_mean": self.UU_mean, "UU_std": self.UU_std,
            "UU_min": self.UU_min,   "UU_max": self.UU_max,
            "UU_cv": self.UU_cv,
            "DU_mean": self.DU_mean, "DU_std": self.DU_std,
            "DU_min": self.DU_min,   "DU_max": self.DU_max,
            "DU_cv": self.DU_cv,
        }


@event.listens_for(UsersVector, "before_insert")
def _autofill_username_from_user_id(mapper, connection, target: UsersVector):
    """Auto-populate username when only user_id is provided.

    This supports tests and legacy data flows where KeystrokeVector rows were
    created with only user_id.
    """
    try:
        if getattr(target, "username", None):
            return
        uid = getattr(target, "user_id", None)
        if not uid:
            return
        row = connection.execute(select(User.username).where(User.id == uid)).first()
        if row and row[0]:
            target.username = row[0]
    except Exception:
        # Best-effort only
        return


def _coerce_loaded_timestamp_to_datetime(target: UsersVector) -> None:
    ts = getattr(target, "timestamp", None)
    if not isinstance(ts, str):
        return
    try:
        parsed = datetime.fromisoformat(ts)
    except Exception:
        return
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    set_committed_value(target, "timestamp", parsed)


@event.listens_for(UsersVector, "load")
def _coerce_timestamp_on_load(target, context):
    _coerce_loaded_timestamp_to_datetime(target)


@event.listens_for(UsersVector, "refresh")
def _coerce_timestamp_on_refresh(target, context, attrs):
    _coerce_loaded_timestamp_to_datetime(target)


# Backward-compatibility alias
KeystrokeVector = UsersVector
