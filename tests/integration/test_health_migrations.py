"""Integration tests for /health/migrations endpoint"""

import pytest

from app.models import db


class FakeInspector:
    def __init__(self, cols, has_users=True):
        self._cols = cols
        self._has_users = has_users

    def get_table_names(self):
        return ["users"] if self._has_users else []

    def get_columns(self, table_name):
        return [{"name": c} for c in self._cols]


def test_health_migrations_ok(client, monkeypatch):
    """When required columns are present, endpoint returns 200 and ok status"""
    cols = ["id", "username", "email", "email_verified", "two_factor_enabled"]
    monkeypatch.setattr(db, "inspect", lambda engine: FakeInspector(cols))

    resp = client.get("/health/migrations")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert "checked_columns" in data


def test_health_migrations_missing_columns(client, monkeypatch):
    """When the migrations are out-of-date (missing columns), return 503 and helpful message"""
    # Inspector reports users table but missing the critical columns
    cols = ["id", "username"]
    monkeypatch.setattr(db, "inspect", lambda engine: FakeInspector(cols))

    resp = client.get("/health/migrations")
    assert resp.status_code == 503
    data = resp.get_json()
    assert data["status"] == "migrations_out_of_date"
    assert "missing_columns" in data
    assert "email" in data["missing_columns"]
    # Message should include an actionable hint to run migrations
    assert "alembic upgrade" in data["message"]
