"""
UsersVector Model - Unified biometric keystroke storage for both register and login.

  event_type = 'enrollment'  → samples captured during registration
  event_type = 'login'       → samples captured during login attempt
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import Index, event, select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm.attributes import set_committed_value

from . import db
from .user import User


class UsersVector(db.Model):
    """
    Unified keystroke biometric storage.
    Used for both enrollment (register) and login verification.
    """

    __tablename__ = "users_vectors"

    __table_args__ = (
        Index("idx_vector_user_event_type", "user_id", "event_type"),
        Index("idx_vector_username_event", "username", "event_type"),
        Index("idx_vector_user_timestamp", "user_id", "timestamp"),
    )

    # --- Primary key ---
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # --- Identity ---
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    username = db.Column(db.Text, nullable=True, index=True)
    timestamp = db.Column(
        db.Text,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).isoformat(),
        index=True,
    )
    password_hash = db.Column(db.Text, nullable=True)

    # --- Status ---
    is_successful = db.Column(db.Boolean, nullable=False, default=True)
    
    # event_type is the canonical discriminator
    event_type = db.Column(db.Text, nullable=True, index=True)  # 'enrollment' | 'login'

    @hybrid_property
    def data_type(self):
        """Legacy alias for event_type."""
        return self.event_type

    @data_type.setter
    def data_type(self, value):
        self.event_type = value

    # --- Aggregate timing ---
    total_duration = db.Column(db.Float, nullable=True)
    typing_speed = db.Column(db.Float, nullable=True)

    # --- Raw timing vectors (JSON arrays) ---
    H_vector  = db.Column(db.Text, nullable=True)
    DD_vector = db.Column(db.Text, nullable=True)
    UD_vector = db.Column(db.Text, nullable=True)
    UU_vector = db.Column(db.Text, nullable=True)
    DU_vector = db.Column(db.Text, nullable=True)

    # --- Per-vector statistics ---
    H_mean = db.Column(db.Float, nullable=True)
    H_std  = db.Column(db.Float, nullable=True)
    H_min  = db.Column(db.Float, nullable=True)
    H_max  = db.Column(db.Float, nullable=True)
    H_cv   = db.Column(db.Float, nullable=True)

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

    def __init__(self, **kwargs):
        """Handle legacy lowercase vector kwargs."""
        legacy_map = {
            "h_vector": "H_vector", "dd_vector": "DD_vector",
            "ud_vector": "UD_vector", "uu_vector": "UU_vector",
            "du_vector": "DU_vector",
        }
        for old, new in legacy_map.items():
            if old in kwargs and new not in kwargs:
                kwargs[new] = kwargs.pop(old)
        
        # event_type / data_type sync handled by hybrid_property during init
        super().__init__(**kwargs)

    def __repr__(self):
        return f"<UsersVector {self.username!r} [{self.event_type}] @ {self.timestamp}>"

    # --- Convenience properties for legacy access ---
    @property
    def h_vector(self): return self.get_vector("H")
    @h_vector.setter
    def h_vector(self, v): self.set_vector("H", v)

    @property
    def dd_vector(self): return self.get_vector("DD")
    @dd_vector.setter
    def dd_vector(self, v): self.set_vector("DD", v)

    @property
    def ud_vector(self): return self.get_vector("UD")
    @ud_vector.setter
    def ud_vector(self, v): self.set_vector("UD", v)

    @property
    def uu_vector(self): return self.get_vector("UU")
    @uu_vector.setter
    def uu_vector(self, v): self.set_vector("UU", v)

    @property
    def du_vector(self): return self.get_vector("DU")
    @du_vector.setter
    def du_vector(self, v): self.set_vector("DU", v)

    def get_vector(self, name: str) -> list:
        raw = getattr(self, f"{name}_vector", None)
        if raw is None: return []
        if isinstance(raw, list): return raw
        try: return json.loads(raw)
        except: return []

    def set_vector(self, name: str, values: list) -> None:
        setattr(self, f"{name}_vector", json.dumps(values) if values is not None else None)

    @property
    def is_enrollment(self): return self.event_type == "enrollment"

    @property
    def is_login(self): return self.event_type == "login"

    def to_dict(self) -> dict:
        ts = self.timestamp
        if isinstance(ts, datetime): ts = ts.isoformat()
        return {
            "id": self.id, "username": self.username, "timestamp": ts,
            "event_type": self.event_type, "total_duration": self.total_duration,
            "typing_speed": self.typing_speed,
            "H_mean": self.H_mean, "H_std": self.H_std, "H_cv": self.H_cv,
            "DD_mean": self.DD_mean, "DD_std": self.DD_std, "DD_cv": self.DD_cv,
            "UD_mean": self.UD_mean, "UD_std": self.UD_std, "UD_cv": self.UD_cv,
            "UU_mean": self.UU_mean, "UU_std": self.UU_std, "UU_cv": self.UU_cv,
            "DU_mean": self.DU_mean, "DU_std": self.DU_std, "DU_cv": self.DU_cv,
        }


@event.listens_for(UsersVector, "before_insert")
def _autofill_username(mapper, connection, target: UsersVector):
    if not target.username and target.user_id:
        row = connection.execute(select(User.username).where(User.id == target.user_id)).first()
        if row: target.username = row[0]


def _coerce_ts(target: UsersVector) -> None:
    ts = getattr(target, "timestamp", None)
    if isinstance(ts, str):
        try:
            parsed = datetime.fromisoformat(ts)
            if parsed.tzinfo is None: parsed = parsed.replace(tzinfo=timezone.utc)
            set_committed_value(target, "timestamp", parsed)
        except: pass


@event.listens_for(UsersVector, "load")
def _on_load(target, context): _coerce_ts(target)


@event.listens_for(UsersVector, "refresh")
def _on_refresh(target, context, attrs): _coerce_ts(target)


KeystrokeVector = UsersVector
