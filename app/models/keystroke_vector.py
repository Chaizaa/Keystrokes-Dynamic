"""
Keystroke Vector Model - Biometric keystroke samples
"""
from datetime import datetime, timezone
from . import db
import json


class KeystrokeVector(db.Model):
    """
    Keystroke biometric vector storage
    
    Stores timing features for keystroke dynamics:
    - H (Hold Time): Duration of key press
    - DD (Down-Down): Time between key presses
    - UD (Up-Down): Time between key release and next press
    - UU (Up-Up): Time between key releases
    - DU (Down-Up): Time between key press and release
    
    Supports both legacy vector format and new character-labeled features
    """
    __tablename__ = 'user_vectors'
    
    # Composite indexes for common query patterns
    __table_args__ = (
        db.Index('idx_vector_user_event_type', 'user_id', 'event_type'),
        db.Index('idx_vector_username_event', 'username', 'event_type'),
        db.Index('idx_vector_user_timestamp', 'user_id', 'timestamp'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    username = db.Column(db.String(80), nullable=False, index=True)  # Denormalized for query speed
    
    # Event metadata
    event_type = db.Column(db.String(50), nullable=False, index=True)  # 'enrollment', 'login_attempt'
    is_successful = db.Column(db.Boolean, default=True, nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    # Password (for keystroke matching)
    password = db.Column(db.String(255), nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)
    
    # Legacy vectors (backward compatibility)
    H_vector = db.Column(db.Text, nullable=True)  # JSON array
    DD_vector = db.Column(db.Text, nullable=True)
    UD_vector = db.Column(db.Text, nullable=True)
    UU_vector = db.Column(db.Text, nullable=True)
    DU_vector = db.Column(db.Text, nullable=True)
    
    # New character-labeled features (JSON)
    H_features = db.Column(db.Text, nullable=True)  # {"H.a_0": 0.123, ...}
    DD_features = db.Column(db.Text, nullable=True)
    UD_features = db.Column(db.Text, nullable=True)
    UU_features = db.Column(db.Text, nullable=True)
    DU_features = db.Column(db.Text, nullable=True)
    
    # Statistical features
    mean_H = db.Column(db.Float, nullable=True)
    std_H = db.Column(db.Float, nullable=True)
    mean_DD = db.Column(db.Float, nullable=True)
    std_DD = db.Column(db.Float, nullable=True)
    mean_UD = db.Column(db.Float, nullable=True)
    std_UD = db.Column(db.Float, nullable=True)
    
    # Advanced statistics
    skew_H = db.Column(db.Float, nullable=True)
    kurtosis_H = db.Column(db.Float, nullable=True)
    median_H = db.Column(db.Float, nullable=True)
    iqr_H = db.Column(db.Float, nullable=True)
    
    # Quality metrics
    sample_quality = db.Column(db.Float, nullable=True)
    quality_warnings = db.Column(db.Text, nullable=True)  # JSON array
    
    # Password strength metrics
    password_strength = db.Column(db.String(50), nullable=True)  # 'weak', 'medium', 'strong'
    password_score = db.Column(db.Float, nullable=True)
    
    # Metadata
    raw_events = db.Column(db.Text, nullable=True)  # JSON array of keystroke events
    session_id = db.Column(db.String(100), nullable=True)
    
    def __repr__(self):
        return f'<KeystrokeVector {self.username} - {self.event_type} @ {self.timestamp}>'
    
    def get_H_vector(self):
        """Parse H_vector from JSON string"""
        if self.H_vector:
            try:
                return json.loads(self.H_vector)
            except:
                return []
        return []
    
    def set_H_vector(self, vector):
        """Set H_vector as JSON string"""
        self.H_vector = json.dumps(vector) if vector else None
    
    def get_H_features(self):
        """Parse H_features from JSON string"""
        if self.H_features:
            try:
                return json.loads(self.H_features)
            except:
                return {}
        return {}
    
    def set_H_features(self, features):
        """Set H_features as JSON string"""
        self.H_features = json.dumps(features) if features else None
    
    def get_quality_warnings(self):
        """Parse quality warnings from JSON"""
        if self.quality_warnings:
            try:
                return json.loads(self.quality_warnings)
            except:
                return []
        return []
    
    def set_quality_warnings(self, warnings):
        """Set quality warnings as JSON"""
        self.quality_warnings = json.dumps(warnings) if warnings else None
    
    def get_raw_events(self):
        """Parse raw keystroke events from JSON"""
        if self.raw_events:
            try:
                return json.loads(self.raw_events)
            except:
                return []
        return []
    
    def set_raw_events(self, events):
        """Set raw events as JSON"""
        self.raw_events = json.dumps(events) if events else None

    def __init__(self, **kwargs):
        # Accept legacy keys and map them to current attribute names
        if 'data_type' in kwargs and 'event_type' not in kwargs:
            kwargs['event_type'] = kwargs.pop('data_type')
        # Accept lower-case vector keys used in tests
        if 'h_vector' in kwargs:
            kwargs['H_vector'] = kwargs.pop('h_vector')
        if 'dd_vector' in kwargs:
            kwargs['DD_vector'] = kwargs.pop('dd_vector')
        if 'ud_vector' in kwargs:
            kwargs['UD_vector'] = kwargs.pop('ud_vector')
        if 'uu_vector' in kwargs:
            kwargs['UU_vector'] = kwargs.pop('uu_vector')
        if 'du_vector' in kwargs:
            kwargs['DU_vector'] = kwargs.pop('du_vector')

        # Auto-populate username when only user_id is provided to support tests
        if 'username' not in kwargs and 'user_id' in kwargs:
            try:
                from .user import User
                user_id = kwargs.get('user_id')
                # Use session.get if available, otherwise fallback to a safe query (avoid deprecated Query.get)
                try:
                    user = db.session.get(User, user_id)
                except Exception:
                    try:
                        from sqlalchemy import select
                        user = db.session.execute(select(User).where(User.id == user_id)).scalars().one_or_none()
                    except Exception:
                        user = None
                if user:
                    kwargs['username'] = user.username
            except Exception:
                # Best effort; if lookup fails, leave username unset and ORM may raise on commit
                pass

        super().__init__(**kwargs)

    # Backwards-compatible properties (accept lower-case names in tests)
    @property
    def h_vector(self):
        return self.get_H_vector()

    @h_vector.setter
    def h_vector(self, value):
        self.set_H_vector(value)

    @property
    def dd_vector(self):
        return json.loads(self.DD_vector) if self.DD_vector else []

    @dd_vector.setter
    def dd_vector(self, value):
        self.DD_vector = json.dumps(value) if value else None

    @property
    def ud_vector(self):
        return json.loads(self.UD_vector) if self.UD_vector else []

    @ud_vector.setter
    def ud_vector(self, value):
        self.UD_vector = json.dumps(value) if value else None

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'username': self.username,
            'event_type': self.event_type,
            'is_successful': self.is_successful,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'sample_quality': self.sample_quality,
            'password_strength': self.password_strength,
            'mean_H': self.mean_H,
            'std_H': self.std_H,
            'quality_warnings': self.get_quality_warnings()
        }
