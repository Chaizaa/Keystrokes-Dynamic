"""
User Model - User accounts with password management
"""

from datetime import datetime, timezone
import hashlib

from flask_login import UserMixin
from sqlalchemy import select, func, event as _sa_event
from werkzeug.security import check_password_hash, generate_password_hash

import uuid6
from sqlalchemy.dialects.postgresql import UUID

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

    __tablename__ = "users"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=lambda: uuid6.uuid7())
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)  # Nullable for migration
    # Role: 'user' or 'admin'
    role = db.Column(db.String(10), nullable=False, server_default="user")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Email verification fields (stateless tokens: no token column)
    email = db.Column(db.String(255), nullable=True, index=True)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    email_verification_sent_at = db.Column(db.DateTime, nullable=True)
    # Hashed short code (6-digit) used for verification when short-code flow is enabled
    email_verification_code_hash = db.Column(db.String(255), nullable=True)

    # Password-reset fields (separate from email-verification so the two flows don't collide).
    # Used by both admin-initiated reset (signed-URL token) and user-initiated reset (6-digit code).
    password_reset_sent_at = db.Column(db.DateTime, nullable=True)
    password_reset_code_hash = db.Column(db.String(255), nullable=True)

    # Two-Factor Authentication fields
    two_factor_enabled = db.Column(db.Boolean, default=False, nullable=False)
    two_factor_secret = db.Column(db.String(255), nullable=True)

    # Login tracking
    last_login = db.Column(db.DateTime(timezone=True), nullable=True)
    last_login_ip = db.Column(db.String(45), nullable=True)  # IPv6 max 45 chars

    # Password strength metadata (mirrors users_vectors aggregate)
    password_strength = db.Column(db.String(32), nullable=True)   # 'weak', 'medium', 'strong'
    password_score = db.Column(db.Integer, nullable=True)
    password_details = db.Column(db.JSON, nullable=True)          # JSON object

    # Relationship to keystroke enrollment vectors (read-only, joined via username)
    enrollment_vectors = db.relationship(
        "UsersVector",
        primaryjoin="User.username == foreign(UsersVector.username)",
        viewonly=True,
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<User {self.username}>"

    def set_password(self, password):
        """
        Set user password (hashed with scrypt - modern algorithm)

        Args:
            password: Plain text password
            
        Note:
            New passwords use scrypt algorithm.
            Existing SHA-256 hashes from CSV are still supported for verification.
        """
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """
        Verify password against hash.

        Supports all modern werkzeug-generated hashes (scrypt, pbkdf2, argon2).

        Legacy unsalted SHA-256 hashes (64 hex chars, no salt) are intentionally
        no longer accepted — they are vulnerable to rainbow-table attacks.
        Any account in that format must go through the password-reset flow to
        obtain a properly hashed password before logging in again.
        """
        if not self.password_hash:
            return False

        # Reject unsalted SHA-256 — do not allow these to authenticate.
        if len(self.password_hash) == 64 and all(c in "0123456789abcdef" for c in self.password_hash):
            return False

        # All modern werkzeug-generated hashes (scrypt, pbkdf2, argon2, etc.)
        return check_password_hash(self.password_hash, password)

    def get_enrollment_count(self) -> int:
        """
        Get number of enrollment samples for this user from users_vectors.

        Returns:
            int: count of enrollment samples
        """
        try:
            from .keystroke_vector import UsersVector

            count = db.session.execute(
                select(func.count()).select_from(UsersVector).where(
                    UsersVector.username == self.username,
                    UsersVector.event_type == "enrollment",
                )
            ).scalar_one()
            return int(count)
        except Exception:
            return 0

    def get_enrollment_samples(self) -> list:
        """
        Get all enrollment samples for this user from users_vectors.

        Returns:
            list[dict]: rows from users_vectors where data_type='enrollment', ordered by newest first
        """
        try:
            from .keystroke_vector import UsersVector

            rows = db.session.execute(
                select(UsersVector).where(
                    UsersVector.username == self.username,
                    UsersVector.event_type == "enrollment",
                ).order_by(UsersVector.id.desc())
            ).scalars().all()
            return [r.to_dict() for r in rows]
        except Exception:
            return []

    def is_admin(self) -> bool:
        """Return True if user is an admin. Default: False (can be overridden later)."""
        try:
            return str(self.role).lower() == "admin"
        except Exception:
            return False

    def to_dict(self):
        """
        Convert user to dictionary (for API responses)

        Returns:
            dict: User data (without sensitive fields)
        """
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "email_verified": bool(self.email_verified),
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "enrollment_count": self.get_enrollment_count(),
            "has_password": bool(self.password_hash),
        }
