"""Test /api/check_username returns resumable when user exists but enrollment incomplete"""

import pytest


def test_check_username_resumable_existing_user(client, monkeypatch):
    from app.blueprints.api import auth_service, biometric_service

    # Simulate auth service reporting user exists
    def fake_availability(username):
        return {
            'available': False,
            'exists': True,
            'reason': 'already_exists',
            'message': f"Username '{username}' is already taken"
        }

    monkeypatch.setattr(auth_service, 'check_username_availability', fake_availability)
    # Simulate biometric service shows partial enrollment
    monkeypatch.setattr(biometric_service, 'get_enrollment_status', lambda u: {'count': 5, 'ready_for_login': False, 'enrolled': False})

    resp = client.post('/api/check_username', json={'username': 'existing_user', 'mode': 'register'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['status'] == 'resumable'
    assert data['exists'] is True
    assert data['enrollment_count'] == 5
    assert 'Resume registration' in data['message']
