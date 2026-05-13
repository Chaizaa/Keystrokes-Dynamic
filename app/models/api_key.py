"""
API Key Model - Store API credentials for partner integrations
"""

import secrets
from datetime import datetime, timedelta, timezone

from . import db

import uuid6
from .types import GUID


class APIKey(db.Model):
    """
    API Key model for partner authentication

    Attributes:
        id: Primary key
        user_id: Foreign key to users table (admin who created this key)
        partner_name: Name of the partner organization
        key_prefix: First 20 chars of key for display (sk_...)
        key_hash: Hashed API key (for security)
        description: Human-readable description of this key
        is_active: Whether this key is currently active
        rate_limit: Request limit per hour (e.g., 100)
        enrolled_users: Number of users enrolled via this API key
        created_at: When key was generated
        last_used_at: Last successful API request timestamp
        expires_at: Optional expiration date
        allowed_origins: Comma-separated list of allowed domains (CORS)
    """

    __tablename__ = "api_keys"

    __table_args__ = (
        db.Index("idx_api_keys_partner_active", "partner_name", "is_active"),
        db.Index("idx_api_keys_user_active", "user_id", "is_active"),
        db.Index("idx_api_keys_prefix", "key_prefix"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(GUID, db.ForeignKey("users.id"), nullable=False, index=True)

    # Partner information
    partner_name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # Key storage (secure)
    key_prefix = db.Column(db.String(20), nullable=False, index=True)  # e.g., "sk_test_abc123"
    key_hash = db.Column(db.String(255), nullable=False)  # Hashed with bcrypt
    
    # Status management
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    
    # Rate limiting
    rate_limit = db.Column(db.Integer, default=100, nullable=False)  # requests per hour
    
    # Usage statistics
    enrolled_users = db.Column(db.Integer, default=0, nullable=False)
    total_enrollments = db.Column(db.Integer, default=0, nullable=False)
    total_verifications = db.Column(db.Integer, default=0, nullable=False)
    
    # Timestamps
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_used_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)  # Optional: set to expire keys
    
    # Security
    allowed_origins = db.Column(db.Text, nullable=True)  # CSV format: "partner.com,app.partner.com"
    
    # Relationships
    user = db.relationship("User", backref="api_keys")
    enrollment_logs = db.relationship(
        "EnrollmentLog",
        back_populates="api_key",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    verification_logs = db.relationship(
        "VerificationLog",
        back_populates="api_key",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<APIKey {self.key_prefix} for {self.partner_name}>"

    @staticmethod
    def generate_key():
        """
        Generate a new API key with secure random token
        
        Returns:
            tuple: (full_key, key_prefix, key_hash)
                - full_key: The complete key to give to partner (e.g., "sk_live_abc123...")
                - key_prefix: First 20 chars (for display, e.g., "sk_live_abc123")
                - key_hash: Hashed key (stored in DB)
        """
        # Generate random token (32 bytes = 256 bits of entropy)
        random_token = secrets.token_urlsafe(32)
        
        # Create full key with prefix
        full_key = f"sk_live_{random_token}"
        
        # Extract prefix (first 20 chars for display)
        key_prefix = full_key[:20]
        
        # Hash the key for storage
        from werkzeug.security import generate_password_hash
        key_hash = generate_password_hash(full_key)
        
        return full_key, key_prefix, key_hash

    def check_key(self, provided_key):
        """
        Verify if provided key matches this API key
        
        Args:
            provided_key: The API key provided in request
            
        Returns:
            bool: True if key matches
        """
        from werkzeug.security import check_password_hash
        return check_password_hash(self.key_hash, provided_key)

    def is_valid(self):
        """
        Check if API key is valid and not expired
        
        Returns:
            bool: True if key can be used
        """
        if not self.is_active:
            return False
        
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False
        
        return True

    def get_remaining_quota(self):
        """
        Get remaining request quota for this hour
        
        Returns:
            int: Remaining requests allowed
        """
        from app.models import EnrollmentLog, VerificationLog
        
        # Get requests count in last hour
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        recent_requests = VerificationLog.query.filter(
            VerificationLog.api_key_id == self.id,
            VerificationLog.timestamp >= one_hour_ago
        ).count()
        
        recent_requests += EnrollmentLog.query.filter(
            EnrollmentLog.api_key_id == self.id,
            EnrollmentLog.timestamp >= one_hour_ago
        ).count()
        
        remaining = max(0, self.rate_limit - recent_requests)
        return remaining

    def update_last_used(self):
        """Update last_used_at timestamp"""
        self.last_used_at = datetime.now(timezone.utc)
        db.session.commit()
