"""API authentication decorator using encrypted API secrets.

Protocol:
- Client sends headers: `X-API-KEY`, `X-API-SIGNATURE`, `X-TIMESTAMP`.
- The server looks up the credential by `api_key`, decrypts the stored
    `api_secret_encrypted` using Fernet, and uses the raw secret as the HMAC key.

Signed message = timestamp + request_body (raw bytes)
Signature = HMAC_SHA256(key=raw_secret, message)

Security notes:
- Timestamp must be within 5 minutes to avoid replay attacks.
- Use `hmac.compare_digest` to avoid timing attacks.
"""
from functools import wraps
from datetime import datetime, timezone
import time
import hmac
import hashlib

from flask import request, jsonify, g, current_app

from app.models import db, APICredential
from app.utils.crypto import decrypt_secret


def require_api_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        api_key = request.headers.get("X-API-KEY")
        signature = request.headers.get("X-API-SIGNATURE")
        timestamp = request.headers.get("X-TIMESTAMP")

        if not api_key or not signature or not timestamp:
            return jsonify({"success": False, "message": "Missing authentication headers"}), 401

        # Lookup credential
        cred = db.session.query(APICredential).filter_by(api_key=api_key, is_active=True).first()
        if not cred:
            return jsonify({"success": False, "message": "Invalid API key"}), 401

        # Validate timestamp - accept integer unix seconds
        try:
            ts = int(timestamp)
        except Exception:
            return jsonify({"success": False, "message": "Invalid timestamp format"}), 401

        now_ts = int(datetime.now(timezone.utc).timestamp())
        # Reject if timestamp difference > 5 minutes (300 seconds)
        if abs(now_ts - ts) > 300:
            return jsonify({"success": False, "message": "Timestamp outside allowed window"}), 401

        # Reconstruct message: timestamp (string) + request body bytes
        try:
            body = request.get_data() or b""
            msg = str(ts).encode("utf-8") + body
        except Exception:
            msg = str(ts).encode("utf-8")

        # Decrypt stored secret and use raw secret as HMAC key
        raw_secret = None
        try:
            raw_secret = decrypt_secret(cred.api_secret_encrypted)
        except Exception:
            raw_secret = None

        if not raw_secret:
            return jsonify({"success": False, "message": "Server misconfiguration"}), 500

        expected_sig = hmac.new(raw_secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

        # Constant time compare
        if not hmac.compare_digest(expected_sig, signature):
            return jsonify({"success": False, "message": "Invalid signature"}), 403

        # Update last_used_at for auditing
        try:
            cred.last_used_at = datetime.now(timezone.utc)
            db.session.commit()
        except Exception:
            db.session.rollback()

        # Attach credential to flask.g for handlers
        g.api_credential = cred
        return fn(*args, **kwargs)

    return wrapper
