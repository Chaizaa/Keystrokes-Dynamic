"""
LoginAttempt model
==================

Immutable record of every login attempt (success or failure).
Used for rate-limiting analysis, security auditing, and fraud detection.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import Index, func, select

from . import db

import uuid6
from sqlalchemy.dialects.postgresql import UUID

class LoginAttempt(db.Model):
    """Per-request login attempt log.

    Columns
    -------
    id                  Primary key
    user_id             FK to users (nullable for unknown users)
    username            Attempted username (always populated)
    success             True = login accepted, False = rejected
    timestamp           UTC timestamp of the attempt
    verification_score  Biometric confidence score (0.0–1.0)
    verification_method How biometric check was performed
    failure_reason      Why login failed (null on success)
    ip_address          Client IP address
    user_agent          Browser / client user-agent header
    session_id          Flask session ID at time of attempt
    attempts_in_window  Failed attempts by this user in the last window
    rate_limit_hit      Whether the rate-limit threshold was triggered
    biometric_tier      Biometric security tier ('tier1', 'tier2', …)
    """

    __tablename__ = "login_attempts"

    __table_args__ = (
        Index("idx_login_username_timestamp", "username", "timestamp"),
        Index("idx_login_username_success", "username", "success"),
        Index("idx_login_user_timestamp", "user_id", "timestamp"),
        Index("idx_login_ip_timestamp", "ip_address", "timestamp"),
    )

    # --- Primary key ---
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # --- Identity ---
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    username = db.Column(db.Text, nullable=False, index=True)

    # --- Result ---
    success = db.Column(db.Boolean, nullable=False, default=False)
    timestamp = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    # --- Biometric details ---
    verification_score = db.Column(db.Float, nullable=True)
    verification_method = db.Column(db.Text, nullable=True)
    biometric_tier = db.Column(db.Text, nullable=True)

    # --- Failure info ---
    failure_reason = db.Column(db.Text, nullable=True)

    # --- Security / request context ---
    ip_address = db.Column(db.Text, nullable=True)
    user_agent = db.Column(db.Text, nullable=True)
    session_id = db.Column(db.Text, nullable=True)
    attempts_in_window = db.Column(db.Integer, nullable=True, default=0)
    rate_limit_hit = db.Column(db.Boolean, nullable=True, default=False)

    # --- Relationship ---
    user = db.relationship("User", backref=db.backref("login_attempts", lazy="dynamic"),
                           foreign_keys=[user_id])

    # ------------------------------------------------------------------ repr
    def __repr__(self) -> str:
        icon = "✅" if self.success else "❌"
        return f"<LoginAttempt {icon} {self.username!r} @ {self.timestamp}>"

    # ----------------------------------------------------------------- factory
    @classmethod
    def log_attempt(
        cls,
        username: str,
        success: bool,
        *,
        user_id: int | None = None,
        verification_score: float | None = None,
        verification_method: str | None = None,
        failure_reason: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        session_id: str | None = None,
        attempts_in_window: int = 0,
        rate_limit_hit: bool = False,
        biometric_tier: str | None = None,
    ) -> "LoginAttempt":
        """Create and persist a ``LoginAttempt`` record.

        All keyword-only arguments are optional enrichment fields.
        The instance is added to the current session and flushed (but not committed).
        """
        attempt = cls(
            username=username,
            success=success,
            user_id=user_id,
            verification_score=verification_score,
            verification_method=verification_method,
            failure_reason=failure_reason,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            attempts_in_window=attempts_in_window,
            rate_limit_hit=rate_limit_hit,
            biometric_tier=biometric_tier,
        )
        db.session.add(attempt)
        db.session.flush()  # Visible within current transaction; caller commits
        return attempt

    # ----------------------------------------------------------- class queries
    @classmethod
    def get_recent_failed_attempts(cls, username: str, minutes: int = 15) -> int:
        """Return the count of failed attempts for *username* in the last *minutes*."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        try:
            count = db.session.execute(
                select(func.count())
                .select_from(cls)
                .where(
                    cls.username == username,
                    cls.success == False,  # noqa: E712
                    cls.timestamp >= cutoff,
                )
            ).scalar_one()
            return int(count)
        except Exception:
            return 0

    # --------------------------------------------------------------- to_dict
    def to_dict(self) -> dict:
        """Serialise to a JSON-safe dict (no sensitive internals)."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.username,
            "success": bool(self.success),
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "verification_score": self.verification_score,
            "verification_method": self.verification_method,
            "failure_reason": self.failure_reason,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "attempts_in_window": self.attempts_in_window,
            "rate_limit_hit": bool(self.rate_limit_hit),
            "biometric_tier": self.biometric_tier,
        }
