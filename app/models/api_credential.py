"""
APICredential model - stores API keys metadata and hashed secret.

Security decisions:
- Raw secret is never stored. We store SHA256(secret_raw) as `api_secret_hash`.
- HMAC verification uses the stored `api_secret_hash` as the HMAC key. This
  allows verification without keeping the raw secret in the database while
  enabling the client to compute signatures using the raw secret they received
  at generation time.
"""
from datetime import datetime, timezone
import uuid
import secrets
import hashlib

from . import db


class APICredential(db.Model):
    __tablename__ = "api_credentials"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    api_key = db.Column(db.String(128), unique=True, index=True, nullable=False)
    # Backwards-compatible: keep legacy hash as nullable to avoid migration failures
    # The system now prefers `api_secret_encrypted` (Fernet) but some DBs
    # may still have `api_secret_hash` column. Mark it nullable to allow inserts.
    api_secret_hash = db.Column(db.String(64), nullable=True)

    # Encrypted API secret stored via Fernet (never store raw secret).
    # Allow nullable for environments where encryption key is not configured
    # so runtime creation of credentials does not fail; enforce non-null in
    # production via configuration and migration scripts.
    api_secret_encrypted = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_used_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    def __repr__(self):
        return f"<APICredential {self.api_key} user={self.user_id} active={self.is_active}>"

    @staticmethod
    def generate_credentials():
        """Generate a new API key + secret pair and return the raw secret.

        Returns:
            (api_key, api_secret_raw)

        Notes:
            - `api_key` uses prefix 'kb_live_' to make keys identifiable.
            - `api_secret_raw` uses prefix 'kb_sec_'. The raw secret MUST only be
              shown once; we never persist it in plaintext.
        """
        token_key = secrets.token_urlsafe(32)
        token_secret = secrets.token_urlsafe(48)
        api_key = f"kb_live_{token_key}"
        api_secret_raw = f"kb_sec_{token_secret}"
        return api_key, api_secret_raw
