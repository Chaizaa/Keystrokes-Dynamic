"""
Enrollment Log Model - Track API-based enrollment requests
"""

from datetime import datetime, timezone

from . import db

import uuid6
from .types import GUID

class EnrollmentLog(db.Model):
    """
    Log for enrollment requests via API

    Attributes:
        id: Primary key
        api_key_id: Foreign key to api_keys table
        user_id: Foreign key to users table (if user exists)
        username: Username being enrolled
        email: Email associated with enrollment
        samples_count: Number of keystroke samples provided
        status: 'pending', 'processing', 'success', 'failed'
        error_message: Error details if status is 'failed'
        enrollment_id: Unique enrollment tracking ID
        client_ip: Client IP address (for audit)
        timestamp: Request timestamp
    """

    __tablename__ = "enrollment_logs"

    __table_args__ = (
        db.Index("idx_enrollment_api_key_timestamp", "api_key_id", "timestamp"),
        db.Index("idx_enrollment_user_timestamp", "user_id", "timestamp"),
        db.Index("idx_enrollment_username_timestamp", "username", "timestamp"),
        db.Index("idx_enrollment_status", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    api_key_id = db.Column(db.Integer, db.ForeignKey("api_keys.id"), nullable=False, index=True)
    user_id = db.Column(GUID, db.ForeignKey("users.id"), nullable=True, index=True)

    # User information
    username = db.Column(db.String(80), nullable=False, index=True)
    email = db.Column(db.String(255), nullable=True)
    
    # Enrollment details
    samples_count = db.Column(db.Integer, nullable=False)
    
    # Status tracking
    status = db.Column(
        db.String(50),
        nullable=False,
        default="pending",
        index=True
    )  # pending, processing, success, failed
    error_message = db.Column(db.Text, nullable=True)
    enrollment_id = db.Column(db.String(100), nullable=True, unique=True, index=True)
    
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
    api_key = db.relationship("APIKey", back_populates="enrollment_logs")
    user = db.relationship("User", backref="api_enrollment_logs")

    def __repr__(self):
        return f"<EnrollmentLog {self.enrollment_id} for {self.username}>"

    def mark_success(self, enrollment_id):
        """Mark enrollment as successful"""
        self.status = "success"
        self.enrollment_id = enrollment_id
        self.error_message = None
        db.session.commit()

    def mark_failed(self, error_message):
        """Mark enrollment as failed with error message"""
        self.status = "failed"
        self.error_message = error_message
        db.session.commit()
