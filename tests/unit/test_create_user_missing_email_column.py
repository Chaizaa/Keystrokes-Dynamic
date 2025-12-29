"""
Ensure create_user works when 'email' column is missing from the users table.
"""
import pytest
from sqlalchemy import inspect


def test_create_user_ignores_missing_email_column(monkeypatch, auth_service, db_session):
    # Simulate inspector reporting columns without 'email'
    real_inspect = inspect

    class FakeInspector:
        def __init__(self, engine):
            pass
        def get_columns(self, table_name):
            return [
                {'name': 'id'}, {'name': 'username'}, {'name': 'password_hash'},
                {'name': 'plain_password'}, {'name': 'created_at'}, {'name': 'updated_at'}
            ]

    import sqlalchemy
    from sqlalchemy.engine import Engine
    real_inspect = sqlalchemy.inspect

    def fake_inspect(obj):
        # Only intercept engine inspections
        if isinstance(obj, Engine):
            return FakeInspector(obj)
        return real_inspect(obj)

    monkeypatch.setattr(sqlalchemy, 'inspect', fake_inspect)

    result = auth_service.create_user('missingemail', 'pass123')
    print('create_user result:', result)
    assert result['success'] is True
    assert result['user'] is not None
    # Email should be absent or None on the returned user
    assert not hasattr(result['user'], 'email') or result['user'].email is None
