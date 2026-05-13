"""Admin audit log model"""
from datetime import datetime, timezone

from . import db

import uuid6
from .types import GUID


class AdminAudit(db.Model):
    """
    Immutable audit trail for all significant user and admin actions.

    Attributes:
        user_id: FK to users.id (nullable for anonymous/pre-registration events)
        username: Snapshot of username at time of action (preserved even if user is deleted)
        action: Action type — use AdminAudit.ACTION_* constants
        details: Optional JSON string with additional context
        timestamp: UTC time the action occurred
    """

    __tablename__ = "admin_audit"

    # --- Valid action constants ---
    ACTION_REGISTERED    = "registered"
    ACTION_ENROLLED      = "enrolled"
    ACTION_LOGIN         = "login"
    ACTION_LOGOUT        = "logout"
    ACTION_LOGIN_FAILED  = "login_failed"
    ACTION_PASSWORD_RESET = "password_reset"
    ACTION_EMAIL_VERIFIED = "email_verified"
    ACTION_DELETED       = "deleted"
    ACTION_ROLE_CHANGED  = "role_changed"

    VALID_ACTIONS = {
        ACTION_REGISTERED, ACTION_ENROLLED, ACTION_LOGIN, ACTION_LOGOUT,
        ACTION_LOGIN_FAILED, ACTION_PASSWORD_RESET, ACTION_EMAIL_VERIFIED,
        ACTION_DELETED, ACTION_ROLE_CHANGED,
    }

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(GUID, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    username = db.Column(db.String(80), nullable=True, index=True)
    action = db.Column(db.String(64), nullable=False, index=True)
    details = db.Column(db.JSON, nullable=True)
    timestamp = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )

    # Relationship to User (nullable — audit row survives user deletion)
    user = db.relationship(
        "User",
        backref=db.backref("audit_logs", lazy="dynamic", passive_deletes=True),
        foreign_keys=[user_id],
    )

    def __repr__(self) -> str:
        return f"<AdminAudit {self.action!r} by {self.username!r} @ {self.timestamp}>"

    @classmethod
    def log(cls, action: str, user_id: int = None, username: str = None, details=None) -> "AdminAudit":
        """
        Factory helper: create and add an audit entry to the current session.

        Args:
            action: One of AdminAudit.ACTION_* constants
            user_id: Optional FK to users.id
            username: Optional username snapshot
            details: Optional dict or string with additional context

        Returns:
            AdminAudit: the unsaved instance (caller must commit)
        """
        entry = cls(
            action=action,
            user_id=user_id,
            username=username,
            details=details,
        )
        db.session.add(entry)
        return entry

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.username,
            "action": self.action,
            "details": self.details,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
