"""Admin audit log model
"""
from datetime import datetime, timezone

from . import db


class AdminAudit(db.Model):
    __tablename__ = "admin_audit"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    username = db.Column(db.String(80), nullable=True, index=True)
    action = db.Column(db.String(64), nullable=False)  # e.g., 'registered','enrolled','login'
    details = db.Column(db.Text, nullable=True)
    timestamp = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.username,
            "action": self.action,
            "details": self.details,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
