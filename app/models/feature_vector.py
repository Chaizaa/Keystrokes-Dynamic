"""
FeatureVector and EnrollmentVector SQLAlchemy models
New canonical storage for biometric feature vectors.
"""
from datetime import datetime, timezone
from . import db
import json


class FeatureVector(db.Model):
    __tablename__ = 'feature_vectors'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    username = db.Column(db.String(80), nullable=False, index=True)

    event_type = db.Column(db.String(50), nullable=False, index=True)  # 'enrollment' or 'login'
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    # Core vectors saved as JSON strings
    H_vector = db.Column(db.Text, nullable=True)
    DD_vector = db.Column(db.Text, nullable=True)
    UD_vector = db.Column(db.Text, nullable=True)
    UU_vector = db.Column(db.Text, nullable=True)
    DU_vector = db.Column(db.Text, nullable=True)

    # Processed features
    H_features = db.Column(db.Text, nullable=True)
    DD_features = db.Column(db.Text, nullable=True)

    # Quality / meta
    quality_label = db.Column(db.String(32), nullable=True)
    quality_score = db.Column(db.Float, nullable=True)

    password = db.Column(db.String(255), nullable=True)
    password_strength = db.Column(db.String(32), nullable=True)
    password_score = db.Column(db.Float, nullable=True)

    raw_events = db.Column(db.Text, nullable=True)

    def set_vectors(self, h=None, dd=None, ud=None, uu=None, du=None):
        if h is not None:
            self.H_vector = json.dumps(h)
        if dd is not None:
            self.DD_vector = json.dumps(dd)
        if ud is not None:
            self.UD_vector = json.dumps(ud)
        if uu is not None:
            self.UU_vector = json.dumps(uu)
        if du is not None:
            self.DU_vector = json.dumps(du)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'event_type': self.event_type,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'quality_label': self.quality_label,
            'quality_score': self.quality_score
        }


class EnrollmentVector(FeatureVector):
    __tablename__ = 'enrollment_vectors'
    __mapper_args__ = {'concrete': True}

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    username = db.Column(db.String(80), nullable=False, index=True)
    event_type = db.Column(db.String(50), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    H_vector = db.Column(db.Text, nullable=True)
    DD_vector = db.Column(db.Text, nullable=True)
    UD_vector = db.Column(db.Text, nullable=True)
    UU_vector = db.Column(db.Text, nullable=True)
    DU_vector = db.Column(db.Text, nullable=True)

    H_features = db.Column(db.Text, nullable=True)
    DD_features = db.Column(db.Text, nullable=True)

    quality_label = db.Column(db.String(32), nullable=True)
    quality_score = db.Column(db.Float, nullable=True)

    password = db.Column(db.String(255), nullable=True)
    password_strength = db.Column(db.String(32), nullable=True)
    password_score = db.Column(db.Float, nullable=True)

    raw_events = db.Column(db.Text, nullable=True)
