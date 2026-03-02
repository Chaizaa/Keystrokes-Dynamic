"""
API credential service utilities.

Provides helpers to ensure a user has a credential, rotate, revoke and query.
"""
from datetime import datetime, timezone
from typing import Optional, Tuple

from app.models import db, APICredential
from app.utils.crypto import encrypt_secret, decrypt_secret
from flask import current_app
import hashlib


# Use centralized crypto helpers


def ensure_api_credential(user) -> Optional[Tuple[str, str]]:
    """
    Ensure the `user` has at least one active API credential.

    If the user has no active credential, generate one, persist it, and return
    (api_key, api_secret_raw). The raw secret is only returned here (never stored).

    If the user already has an active credential, return None.
    """
    # Check for any active credentials
    active = [c for c in getattr(user, "api_credentials", []) if c.is_active]
    if active:
        return None

    api_key, api_secret_raw = APICredential.generate_credentials()
    enc = encrypt_secret(api_secret_raw)
    # For compatibility with existing DB schemas that require `api_secret_hash`,
    # compute and store the SHA256 hex digest so inserts do not fail.
    try:
        api_secret_hash = hashlib.sha256(api_secret_raw.encode("utf-8")).hexdigest()
    except Exception:
        api_secret_hash = None
    cred = APICredential(
        user_id=user.id,
        api_key=api_key,
        api_secret_hash=api_secret_hash,
        api_secret_encrypted=enc,
    )
    db.session.add(cred)
    db.session.commit()
    return api_key, api_secret_raw


def get_active_credential_for_user(user) -> Optional[APICredential]:
    """Return the first active APICredential for the user or None."""
    for c in getattr(user, "api_credentials", []) or []:
        if c.is_active:
            return c
    return None


def rotate_credential(user) -> Tuple[str, str]:
    """
    Deactivate existing active credentials and create a new one.

    Returns the new (api_key, api_secret_raw).
    """
    # Deactivate existing
    changed = False
    for c in getattr(user, "api_credentials", []) or []:
        if c.is_active:
            c.is_active = False
            changed = True
    if changed:
        db.session.flush()

    api_key, api_secret_raw = APICredential.generate_credentials()
    enc = encrypt_secret(api_secret_raw)
    try:
        api_secret_hash = hashlib.sha256(api_secret_raw.encode("utf-8")).hexdigest()
    except Exception:
        api_secret_hash = None
    cred = APICredential(
        user_id=user.id,
        api_key=api_key,
        api_secret_hash=api_secret_hash,
        api_secret_encrypted=enc,
    )
    db.session.add(cred)
    db.session.commit()
    return api_key, api_secret_raw


def revoke_credential(user) -> bool:
    """
    Revoke all active credentials for the user. Returns True if anything changed.
    """
    changed = False
    for c in getattr(user, "api_credentials", []) or []:
        if c.is_active:
            c.is_active = False
            changed = True
    if changed:
        db.session.commit()
    return changed
