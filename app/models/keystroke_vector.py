"""
UsersVector Model - Unified biometric keystroke storage for both register and login.

  data_type = 'enrollment'  → samples captured during registration
  data_type = 'login'       → samples captured during login attempt

Schema mirrors biometric_system.db reference exactly.
"""

import json

from sqlalchemy import Index

from . import db


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
    username      = db.Column(db.Text, nullable=True, index=True)
    timestamp     = db.Column(db.Text, nullable=True)
    password_hash = db.Column(db.Text, nullable=True)

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
    data_type = db.Column(db.Text, nullable=True, index=True)  # 'enrollment' | 'login'
    # event_type mirrors data_type so that legacy code using event_type continues to work
    event_type = db.Column(db.Text, nullable=True, index=True)  # alias for data_type

    def __repr__(self):
        return f"<UsersVector {self.username!r} [{self.data_type}] @ {self.timestamp}>"

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
        return self.data_type == "enrollment"

    @property
    def is_login(self) -> bool:
        """True if this sample was captured during a login attempt."""
        return self.data_type == "login"

    def to_dict(self) -> dict:
        """Full dict representation including all statistics for API responses."""
        return {
            "id": self.id,
            "username": self.username,
            "timestamp": self.timestamp,
            "data_type": self.data_type,
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


# Backward-compatibility alias
KeystrokeVector = UsersVector
