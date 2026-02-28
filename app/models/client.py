"""API client model for external service authentication."""

import hashlib
import secrets

from . import db


class Client(db.Model):
    """Represents an external API client authenticated via API key."""

    __tablename__ = "clients"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    api_key_hash = db.Column(db.String(128), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime, default=db.func.now(), nullable=False
    )

    def generate_api_key(self) -> str:
        """Generate a secure random API key.

        The raw key is returned **once** so it can be shown to the caller.
        Only its SHA-256 hash is persisted — the plain-text key is never stored.

        Returns:
            str: The raw API key (pass it to the client; it cannot be recovered).
        """
        raw_key = secrets.token_urlsafe(32)
        self.api_key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        return raw_key

    def __repr__(self) -> str:
        return f"<Client id={self.id} name={self.name!r}>"
