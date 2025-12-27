"""
User Model - User accounts with password management
"""
from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from . import db


class User(UserMixin, db.Model):
    """
    User model for authentication
    
    Attributes:
        id: Primary key
        username: Unique username
        password_hash: Hashed password (bcrypt)
        plain_password: Legacy plain password (for migration, will be removed)
        created_at: Account creation timestamp
        updated_at: Last update timestamp
    """
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)  # Nullable for migration
    # Role: 'user' or 'admin'
    role = db.Column(db.String(10), nullable=False, server_default='user')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Email verification fields (stateless tokens: no token column)
    email = db.Column(db.String(255), nullable=True, index=True)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    email_verification_sent_at = db.Column(db.DateTime, nullable=True)
    # Hashed short code (6-digit) used for verification when short-code flow is enabled
    email_verification_code_hash = db.Column(db.String(128), nullable=True)

    # Two-Factor Authentication fields (keep for now)
    two_factor_enabled = db.Column(db.Boolean, default=False, nullable=False)
    two_factor_secret = db.Column(db.String(255), nullable=True)

    # Relationships
    keystroke_vectors = db.relationship('KeystrokeVector', backref='user', lazy='dynamic',
                                       cascade='all, delete-orphan')
    login_attempts = db.relationship('LoginAttempt', backref='user', lazy='dynamic',
                                    cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    def set_password(self, password):
        """
        Set user password (hashed with bcrypt)
        
        Args:
            password: Plain text password
        """
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """
        Verify password against hash
        
        Args:
            password: Plain text password to verify
            
        Returns:
            bool: True if password matches
        """
        if self.password_hash:
            return check_password_hash(self.password_hash, password)
        return False
    
    def get_enrollment_count(self):
        """
        Get number of enrollment samples for this user
        
        Returns:
            int: Number of enrollment samples
        """
        return self.keystroke_vectors.filter_by(
            event_type='enrollment',
            is_successful=True
        ).count()
    
    def get_enrollment_samples(self):
        """
        Get all successful enrollment samples
        
        Returns:
            list: KeystrokeVector objects
        """
        return self.keystroke_vectors.filter_by(
            event_type='enrollment',
            is_successful=True
        ).all()
    
    def is_admin(self) -> bool:
        """Return True if user is an admin. Default: False (can be overridden later)."""
        return False

    def to_dict(self):
        """
        Convert user to dictionary (for API responses)
        
        Returns:
            dict: User data (without sensitive fields)
        """
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'email_verified': bool(self.email_verified),
            'role': self.role,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'enrollment_count': self.get_enrollment_count(),
            'has_password': bool(self.password_hash)
        }
