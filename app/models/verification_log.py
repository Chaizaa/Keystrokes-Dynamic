"""
Verification Log Model - Track API-based verification requests
"""

from datetime import datetime, timezone

from . import db

import uuid6
from .types import GUID

class VerificationLog(db.Model):
    """
    Log for verification requests via API

    Attributes:
        id: Primary key
        api_key_id: Foreign key to api_keys table
        user_id: Foreign key to users table
        username: Username being verified
        verified: Whether verification succeeded
        confidence_score: Biometric match confidence (0.0 - 1.0)
        error_message: Error details if verification failed
        client_ip: Client IP address (for audit)
        timestamp: Request timestamp
    """

    __tablename__ = "verification_logs"

    __table_args__ = (
        db.Index("idx_verification_api_key_timestamp", "api_key_id", "timestamp"),
        db.Index("idx_verification_user_timestamp", "user_id", "timestamp"),
        db.Index("idx_verification_username_timestamp", "username", "timestamp"),
        db.Index("idx_verification_verified", "verified"),
    )

    id = db.Column(db.Integer, primary_key=True)
    api_key_id = db.Column(db.Integer, db.ForeignKey("api_keys.id"), nullable=False, index=True)
    user_id = db.Column(GUID, db.ForeignKey("users.id"), nullable=True, index=True)

    # User information
    username = db.Column(db.String(80), nullable=False, index=True)
    
    # Verification result
    verified = db.Column(db.Boolean, nullable=False, index=True)
    confidence_score = db.Column(db.Float, nullable=True)  # 0.0 to 1.0
    error_message = db.Column(db.Text, nullable=True)  # Error if verification failed
    
    # Audit trail
    client_ip = db.Column(db.String(45), nullable=True)  # IPv4 or IPv6
    user_agent = db.Column(db.String(255), nullable=True)
    
    timestamp = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )
    
    # Relationships
    api_key = db.relationship("APIKey", back_populates="verification_logs")
    user = db.relationship("User", backref="api_verification_logs")

    def __repr__(self):
        return f"<VerificationLog {self.username} ({'verified' if self.verified else 'failed'})>"

    @property
    def status(self):
        """Get status as string"""
        if self.verified:
            return "verified"
        return "failed"
