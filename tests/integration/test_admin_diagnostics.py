"""Integration tests for /admin/diagnostics endpoint"""
import pytest
from app.models import db


class FakeInspector:
    def __init__(self, cols=None, tables=None):
        self._cols = cols or ['id', 'username', 'email', 'email_verified', 'two_factor_enabled']
        self._tables = tables or ['users', 'alembic_version']

    def get_table_names(self):
        return list(self._tables)

    def get_columns(self, table_name):
        if table_name == 'users':
            return [{'name': c} for c in self._cols]
        return []


def test_admin_diagnostics_ok(client, monkeypatch):
    """Diagnostics returns expected keys when DB is reachable"""
    monkeypatch.setattr(db, 'inspect', lambda engine: FakeInspector())

    resp = client.get('/admin/diagnostics')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'timestamp' in data
    assert 'required_user_columns_present' in data
    # alembic_revision may be None in test DB
    assert 'latest_migration_file' in data


def test_admin_diagnostics_db_unreachable(client, monkeypatch):
    """If DB inspection raises, endpoint returns 503"""
    def bad_inspect(engine):
        raise RuntimeError('connection failed')

    monkeypatch.setattr(db, 'inspect', bad_inspect)
    resp = client.get('/admin/diagnostics')
    assert resp.status_code == 503
    data = resp.get_json()
    assert data['status'] == 'error'
    assert 'Database unreachable' in data['message']
