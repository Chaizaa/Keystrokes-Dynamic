"""User ML model persistence.

Stores a per-user keystroke ML classifier (RandomForest) and its EER-based
threshold in the application database.

Why DB storage?
- Matches the requested deployment: model lives in `.db` (or any configured DB)
- Avoids managing per-user `.pkl` files + `thresholds.json`
- Enables automatic training when a user finishes enrollment

The training procedure is implemented to match `ml/ml_pta.py` as closely as
possible (including the EER threshold selection on a validation split).
"""

from __future__ import annotations

from datetime import datetime, timezone

from . import db

import uuid6
from sqlalchemy.dialects.postgresql import UUID

class UserMLModel(db.Model):
    """Per-user ML model artifact + threshold."""

    __tablename__ = "user_ml_models"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    username = db.Column(db.Text, nullable=False, unique=True, index=True)

    # Serialized model bytes (joblib/pickle)
    model_blob = db.Column(db.LargeBinary, nullable=False)

    # EER-based threshold for probabilities
    threshold = db.Column(db.Float, nullable=False)

    # JSON-encoded list of feature column names used in training
    feature_names_json = db.Column(db.Text, nullable=False)

    # Optional metadata/debug
    model_type = db.Column(db.Text, nullable=False, default="RandomForestClassifier")
    sklearn_version = db.Column(db.Text, nullable=True)
    metrics_json = db.Column(db.Text, nullable=True)
    train_params_json = db.Column(db.Text, nullable=True)

    n_samples_total = db.Column(db.Integer, nullable=True)
    n_genuine = db.Column(db.Integer, nullable=True)
    n_impostor = db.Column(db.Integer, nullable=True)

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<UserMLModel {self.username!r} thr={self.threshold:.4f}>"
