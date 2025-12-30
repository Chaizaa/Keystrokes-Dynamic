import pytest


def test_register_sample_save_failure_returns_500(client, monkeypatch, db_session):
    """If DB writer fails (legacy path), API should return 500 not 200."""
    # Mock process_web_events to return success and minimal features
    def fake_process(events, username):
        # Use a stronger password string so password strength validation passes
        return {'status': 'success', 'features': {'H_vector': [0.1,0.12,0.11], 'DD_vector': [0.2,0.22]}, 'real_password_string': 'StrongPass123!', 'password_hash': 'abc'}
    monkeypatch.setattr('app.blueprints.api.process_web_events', fake_process)
    # Ensure a user exists so SQLAlchemy path is exercised
    from app.services.auth_service import AuthService
    auth = AuthService()
    user_res = auth.create_user('savefail', 'StrongPass123!', email=None)
    assert user_res['success'] is True

    # Monkeypatch SQLAlchemy commit to raise an exception to simulate DB failure
    from app.models import db as sqlalchemy_db
    def raise_commit():
        raise Exception('Simulated DB failure')
    monkeypatch.setattr(sqlalchemy_db.session, 'commit', raise_commit)

    payload = {'username': 'savefail', 'events': [{'type':'k','key':'a'}], 'email': None}
    resp = client.post('/api/register_sample', json=payload)
    assert resp.status_code == 500
    data = resp.get_json()
    assert 'Database' in data.get('message') or 'Database error' in data.get('message')
