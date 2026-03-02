"""
User Model - User accounts with password management
"""

from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from . import db
from sqlalchemy import text


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

    id = db.Column(db.Integer, primary_key=True)
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
    email_verification_code_hash = db.Column(db.String(128), nullable=True)

    # Two-Factor Authentication fields (keep for now)
    two_factor_enabled = db.Column(db.Boolean, default=False, nullable=False)
    two_factor_secret = db.Column(db.String(255), nullable=True)

    # Relationships
    keystroke_vectors = db.relationship(
        "KeystrokeVector", backref="user", lazy="dynamic", cascade="all, delete-orphan"
    )
    login_attempts = db.relationship(
        "LoginAttempt", backref="user", lazy="dynamic", cascade="all, delete-orphan"
    )
    # API credentials relationship: each user may have multiple API credentials
    # lazy=True used so accessing `user.api_credentials` returns a list (suitable for templates)
    api_credentials = db.relationship(
        "APICredential",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<User {self.username}>"

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
        # Use a raw SQL COUNT query to avoid selecting all mapped columns
        # (some legacy DBs may lack newer columns like `password` on user_vectors)
        try:
            res = db.session.execute(
                text(
                    "SELECT COUNT(*) AS c FROM user_vectors WHERE user_id = :uid AND event_type = :etype AND is_successful = 1"
                ),
                {"uid": self.id, "etype": "enrollment"},
            )
            return int(res.scalar_one())
        except Exception:
            # Fallback to ORM count in case raw SQL fails for any reason
            try:
                return self.keystroke_vectors.filter_by(event_type="enrollment", is_successful=True).count()
            except Exception:
                return 0

    def get_enrollment_samples(self):
        """
        Get all successful enrollment samples

        Returns:
            list: KeystrokeVector objects
        """
        # The legacy `user_vectors` table may be missing columns that the
        # SQLAlchemy model maps (e.g. `password`). Query a minimal set of
        # fields via raw SQL and return lightweight dicts to avoid mapping
        # errors when reading older DBs.
        try:
            rows = db.session.execute(
                text(
                    "SELECT id, username, event_type, is_successful, timestamp, session_id, raw_events FROM user_vectors "
                    "WHERE user_id = :uid AND event_type = :etype AND is_successful = 1 ORDER BY id DESC"
                ),
                {"uid": self.id, "etype": "enrollment"},
            ).mappings().all()
            # Convert RowMapping to dicts
            return [dict(r) for r in rows]
        except Exception:
            try:
                return self.keystroke_vectors.filter_by(event_type="enrollment", is_successful=True).all()
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
