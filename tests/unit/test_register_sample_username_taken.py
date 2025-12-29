"""Test that /api/register_sample surfaces USERNAME_TAKEN correctly"""


def test_register_sample_user_already_exists(client, monkeypatch, db_session):
    # Simulate AuthService.create_user returning USERNAME_TAKEN
    def fake_create_user(username, password, email=None):
        return {'success': False, 'user': None, 'message': 'Username already exists', 'error_code': 'USERNAME_TAKEN'}

    from app.blueprints.api import auth_service
    monkeypatch.setattr(auth_service, 'create_user', fake_create_user)

    # Provide a minimal valid event stream (two keys with down/up)
    events = [
        {'key':'a','code':'KeyA','evt':'d','t':0},
        {'key':'a','code':'KeyA','evt':'u','t':100},
        {'key':'b','code':'KeyB','evt':'d','t':200},
        {'key':'b','code':'KeyB','evt':'u','t':300}
    ]

    # Ensure biometric service reports zero existing samples so create_user is called
    from app.blueprints.api import biometric_service
    monkeypatch.setattr(biometric_service, 'get_enrollment_status', lambda u: {'count': 0, 'ready_for_login': False, 'enrolled': False})

    # Force password strength to be sufficient so create_user is invoked
    # Monkeypatch the function used by the API module (it imports calculate_password_strength directly)
    import app.blueprints.api as api_module
    monkeypatch.setattr(api_module, 'calculate_password_strength', lambda pw_str: {'strength': 'strong', 'score': 0.9})

    payload = {'username': 'existing', 'events': events, 'email': 'existing@example.com'}
    resp = client.post('/api/register_sample', json=payload)
    assert resp.status_code == 400
    data = resp.get_json()
    assert data['status'] == 'error'
    assert data.get('error_code') == 'USERNAME_TAKEN'
    assert 'exists' in data.get('message').lower() or 'taken' in data.get('message').lower()
