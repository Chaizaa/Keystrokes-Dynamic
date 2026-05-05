"""Service for handling numeric codes and signed tokens for verification flows."""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Any

from flask import current_app
from itsdangerous import BadSignature, URLSafeSerializer
from werkzeug.security import check_password_hash, generate_password_hash

logger = logging.getLogger(__name__)

class VerificationService:
    """Handles generation and validation of verification tokens and 6-digit codes."""

    @staticmethod
    def generate_6_digit_code() -> str:
        """Generate a zero-padded six-digit one-time code."""
        return str(secrets.randbelow(10**6)).zfill(6)

    @staticmethod
    def hash_code(code: str) -> str:
        """Hash a numeric code for secure DB storage."""
        return generate_password_hash(code)

    @staticmethod
    def generate_signed_token(email: str, salt: str = "email-verify", sent_at: Optional[datetime] = None) -> str:
        """Generate a signed, stateless token containing email and timestamp."""
        secret = current_app.config.get("SECRET_KEY")
        serializer = URLSafeSerializer(secret, salt=salt)
        
        ts = sent_at if sent_at is not None else datetime.now(timezone.utc)
        payload = {
            "email": email,
            "sent_at": ts.replace(tzinfo=timezone.utc).isoformat(),
        }
        return serializer.dumps(payload)

    def verify_token(
        self, 
        token: str, 
        email: str, 
        expected_sent_at: Optional[datetime], 
        code_hash: Optional[str] = None, 
        salt: str = "email-verify"
    ) -> Tuple[bool, Optional[str]]:
        """Verify a token (numeric code or signed token).
        
        Returns:
            (True, None) if valid.
            (False, reason) if invalid or expired.
        """
        if not token or not email or not expected_sent_at:
            return False, "invalid"

        # 1. Numeric Code Check (6 digits)
        if len(token) == 6 and token.isdigit():
            if not code_hash:
                return False, "invalid"
            if not check_password_hash(code_hash, token):
                return False, "invalid"
            
            if self._is_expired(expected_sent_at):
                return False, "expired"
            return True, None

        # 2. Signed Token Check
        return self.verify_signed_token(token, email, expected_sent_at, salt=salt)

    def verify_signed_token(
        self, 
        token: str, 
        email: str, 
        expected_sent_at: datetime, 
        salt: str = "email-verify"
    ) -> Tuple[bool, Optional[str]]:
        """Strictly verify a signed token."""
        secret = current_app.config.get("SECRET_KEY")
        serializer = URLSafeSerializer(secret, salt=salt)
        
        try:
            payload = serializer.loads(token)
        except BadSignature:
            return False, "invalid"

        if payload.get("email") != email:
            return False, "invalid"

        token_sent_raw = payload.get("sent_at")
        try:
            token_dt = datetime.fromisoformat(token_sent_raw)
            if token_dt.tzinfo is None:
                token_dt = token_dt.replace(tzinfo=timezone.utc)
        except Exception:
            return False, "invalid"

        # Compare timestamps (allow 60s tolerance for DB precision/skew)
        expected_utc = expected_sent_at.replace(tzinfo=timezone.utc)
        delta = abs(expected_utc.timestamp() - token_dt.timestamp())
        
        if delta > 60:
            logger.debug(f"Token timestamp mismatch: delta={delta}s")
            return False, "invalid"

        if self._is_expired(expected_sent_at):
            return False, "expired"

        return True, None

    @staticmethod
    def _is_expired(sent_at: datetime) -> bool:
        """Check if the timestamp has exceeded the configured expiry hours."""
        expiry_hours = current_app.config.get("EMAIL_VERIFICATION_EXPIRY_HOURS", 1)
        sent_utc = sent_at.replace(tzinfo=timezone.utc) if sent_at.tzinfo is None else sent_at
        return datetime.now(timezone.utc) > (sent_utc + timedelta(hours=int(expiry_hours)))

verification_service = VerificationService()
