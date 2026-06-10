"""Lightweight, dependency-free input validators shared across blueprints."""

from __future__ import annotations

import re

# Pragmatic email pattern: one "@", no whitespace, and a dotted domain.
# Not RFC 5322-exhaustive on purpose — it rejects obvious garbage (e.g. "AAAAAAA")
# without falsely rejecting normal addresses. Authoritative ownership is still
# proven by the 6-digit verification code, so this only needs to catch typos.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MAX_EMAIL_LENGTH = 254  # RFC 5321 limit for the whole address


def is_valid_email(email: str | None) -> bool:
    """Return True if ``email`` looks like a syntactically valid address."""
    if not email or not isinstance(email, str):
        return False
    email = email.strip()
    if len(email) > MAX_EMAIL_LENGTH:
        return False
    return bool(_EMAIL_RE.match(email))
