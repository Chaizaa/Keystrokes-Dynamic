"""Cryptographic helpers for API secret encryption/decryption.

This module centralizes Fernet usage and configuration. The Fernet key
is read from the environment variable `API_SECRET_ENCRYPTION_KEY`.

In production, absence of the env var will raise an error to avoid
operating without encryption.
"""
import os
from typing import Optional

from flask import current_app


def get_fernet():
    try:
        from cryptography.fernet import Fernet
    except Exception:
        return None

    # Prefer explicit configuration from Flask config, fall back to env var
    key = None
    try:
        # Support both config names used in project: `API_SECRET_ENC_KEY` (config.py)
        # and `API_SECRET_ENCRYPTION_KEY` (spec-style). Check both.
        key = current_app.config.get("API_SECRET_ENC_KEY") or current_app.config.get(
            "API_SECRET_ENCRYPTION_KEY"
        )
    except Exception:
        key = None

    if not key:
        key = os.environ.get("API_SECRET_ENC_KEY") or os.environ.get("API_SECRET_ENCRYPTION_KEY")

    # In production, require the key
    env_name = None
    try:
        env_name = current_app.config.get("ENV")
    except Exception:
        pass
    if not key and env_name == "production":
        raise RuntimeError("API_SECRET_ENCRYPTION_KEY must be set in production")

    if not key:
        return None

    try:
        return Fernet(key.encode())
    except Exception:
        return None


def encrypt_secret(raw: str) -> Optional[str]:
    f = get_fernet()
    if not f:
        return None
    try:
        return f.encrypt(raw.encode()).decode()
    except Exception:
        return None


def decrypt_secret(enc: str) -> Optional[str]:
    if not enc:
        return None
    f = get_fernet()
    if not f:
        return None
    try:
        return f.decrypt(enc.encode()).decode()
    except Exception:
        return None
