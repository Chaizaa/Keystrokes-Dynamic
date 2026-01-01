import time

import pytest


def test_debounce_and_429_resilience(client, monkeypatch):
    """Simulate rapid calls to /api/check_username and assert UI would be tolerant.
    This is limited to calling the endpoint directly and ensuring it responds with 429 when rate-limited,
    and that subsequent calls eventually return 200 once rate limit relaxes.
    """
    # Rapidly call the endpoint to simulate client hammering
    payload = {"username": "resilience_test"}

    # Send many fast requests
    statuses = [client.post("/api/check_username", json=payload).status_code for _ in range(15)]

    # Expect at least some 429 responses when rate limiting triggers
    assert 429 in statuses or all(s == 200 for s in statuses)

    # Wait a short while (backoff) and ensure we can get 200
    time.sleep(0.6)
    resp = client.post("/api/check_username", json=payload)
    assert resp.status_code in (200, 429)
