"""Replay-attack defenses for keystroke-based authentication.

Two layers:
  1. Single-use challenge nonces issued via /api/login_challenge.
  2. Recent-payload fingerprint set — identical (username, events) tuples seen
     inside the window are rejected.

The in-memory store is sufficient for single-worker deployments. For multi-
worker / multi-instance deployments, swap the backing dicts for Redis with
the same TTLs (the public API of this module is intentionally tiny).
"""

from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time
from typing import Dict, List, Optional, Tuple

# Nonce stays valid for ~2 minutes — long enough to type a password
# without rushing, short enough that a captured nonce expires quickly.
NONCE_TTL_SECONDS = 120
# Keep payload fingerprints for 10 minutes. Window must outlive the nonce
# window so a replay-with-fresh-nonce is still caught.
FINGERPRINT_TTL_SECONDS = 600

_nonces: Dict[str, Tuple[str, float]] = {}
_seen_fingerprints: Dict[str, float] = {}
_lock = threading.Lock()


def _cleanup_locked(now: float) -> None:
    """Drop expired entries. Caller must hold the lock."""
    expired_nonces = [k for k, (_, exp) in _nonces.items() if exp < now]
    for k in expired_nonces:
        _nonces.pop(k, None)
    expired_fps = [k for k, exp in _seen_fingerprints.items() if exp < now]
    for k in expired_fps:
        _seen_fingerprints.pop(k, None)


def issue_nonce(username: str) -> Tuple[str, float]:
    """Mint a fresh nonce bound to `username`. Returns (nonce, expires_at_epoch)."""
    nonce = secrets.token_urlsafe(32)
    now = time.time()
    expires_at = now + NONCE_TTL_SECONDS
    with _lock:
        _cleanup_locked(now)
        _nonces[nonce] = (username, expires_at)
    return nonce, expires_at


def consume_nonce(username: str, nonce: Optional[str]) -> bool:
    """Atomically validate and consume `nonce`. Returns True on success.

    Fails when the nonce is missing, expired, already consumed, or not bound
    to the requesting username.
    """
    if not nonce:
        return False
    now = time.time()
    with _lock:
        _cleanup_locked(now)
        entry = _nonces.pop(nonce, None)
    if entry is None:
        return False
    bound_username, expires_at = entry
    if expires_at < now:
        return False
    if bound_username != username:
        return False
    return True


def fingerprint(username: str, events: List[dict]) -> str:
    """Stable SHA-256 of `(username, canonical_events)`.

    Two genuine logins produce different millisecond-level timings so their
    fingerprints differ. A bit-for-bit replay produces an identical fingerprint
    and will be caught by `mark_seen_or_replay`.
    """
    canonical = {
        "u": username or "",
        "e": [
            (
                evt.get("evt"),
                evt.get("code"),
                evt.get("key"),
                evt.get("t"),
            )
            for evt in (events or [])
        ],
    }
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def mark_seen_or_replay(payload_hash: str) -> bool:
    """Record `payload_hash` as seen. Returns True if it was already seen."""
    now = time.time()
    with _lock:
        _cleanup_locked(now)
        if payload_hash in _seen_fingerprints:
            return True
        _seen_fingerprints[payload_hash] = now + FINGERPRINT_TTL_SECONDS
    return False


def _stats_for_tests() -> Dict[str, int]:
    """Internal: return current store sizes (used by tests)."""
    with _lock:
        return {"nonces": len(_nonces), "fingerprints": len(_seen_fingerprints)}


def _reset_for_tests() -> None:
    """Internal: wipe state between tests."""
    with _lock:
        _nonces.clear()
        _seen_fingerprints.clear()
