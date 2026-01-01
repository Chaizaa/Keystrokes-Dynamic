"""
Test that create_user returns a friendly error when DB schema is missing columns (OperationalError)
"""

import pytest
from sqlalchemy.exc import OperationalError


def test_create_user_schema_mismatch(monkeypatch, auth_service):
    # Simulate OperationalError when checking existing user
    def fake_execute(stmt):
        raise OperationalError("no such column", None, None)

    monkeypatch.setattr(auth_service, "db", auth_service.db)  # ensure attribute exists
    monkeypatch.setattr(
        "app.services.auth_service.sqlalchemy_db.session.execute",
        lambda stmt: (_ for _ in ()).throw(OperationalError("no such column", None, None)),
    )

    result = auth_service.create_user("userx", "pass")
    assert result["success"] is False
    assert "schema" in result["message"].lower() or "upgrade" in result["message"].lower()
