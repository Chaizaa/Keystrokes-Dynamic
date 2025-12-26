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
    plain_password = db.Column(db.String(255), nullable=True)  # Legacy, will be deprecated
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
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
        # Keep plain_password for backward compatibility during migration
        self.plain_password = password
    
    def check_password(self, password):
        """
        Verify password against hash
        
        Args:
            password: Plain text password to verify
            
        Returns:
            bool: True if password matches
        """
        # Try modern hash first
        if self.password_hash:
            return check_password_hash(self.password_hash, password)
        
        # Fallback to plain password (legacy)
        if self.plain_password:
            return self.plain_password == password
        
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
    
    def to_dict(self):
        """
        Convert user to dictionary (for API responses)
        
        Returns:
            dict: User data (without sensitive fields)
        """
        return {
            'id': self.id,
            'username': self.username,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'enrollment_count': self.get_enrollment_count(),
            'has_password': bool(self.password_hash or self.plain_password)
        }
