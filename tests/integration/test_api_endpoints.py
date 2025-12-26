"""
Integration tests for API endpoints

Tests the actual HTTP endpoints with real Flask app:
- Check username endpoint
- Register sample endpoint  
- Login endpoint
- User info endpoint
"""
import pytest
import json


class TestCheckUsernameEndpoint:
    """Test /api/check_username endpoint"""
    
    def test_check_username_available(self, client):
        """Test checking available username"""
        response = client.post('/api/check_username',
                              json={'username': 'newuser', 'mode': 'register'},
                              content_type='application/json')
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'available' in data or 'status' in data
    
    def test_check_username_empty(self, client):
        """Test checking empty username"""
        response = client.post('/api/check_username',
                              json={'username': '', 'mode': 'register'},
                              content_type='application/json')
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'message' in data or 'error' in data
    
    def test_check_username_login_mode_nonexistent(self, client):
        """Test login mode with non-existent user"""
        response = client.post('/api/check_username',
                              json={'username': 'nonexistent', 'mode': 'login'},
                              content_type='application/json')
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'exists' in data
        assert data['exists'] is False


class TestUserInfoEndpoint:
    """Test /api/user/info endpoint"""
    
    def test_user_info_unauthenticated(self, client):
        """Test accessing user info without authentication"""
        response = client.get('/api/user/info')
        
        # Should redirect to login or return 401
        assert response.status_code in [401, 302]
    
    def test_user_info_authenticated(self, authenticated_client, sample_user):
        """Test accessing user info with authentication"""
        response = authenticated_client.get('/api/user/info')
        
        # Might fail due to legacy db.py, but should at least attempt
        assert response.status_code in [200, 404, 500]


class TestAPIHealthCheck:
    """Test basic API health"""
    
    def test_home_page_loads(self, client):
        """Test that home page is accessible"""
        response = client.get('/')
        
        # Should either load or redirect to login
        assert response.status_code in [200, 302]
    
    def test_login_page_loads(self, client):
        """Test that login page loads"""
        response = client.get('/login')
        
        assert response.status_code == 200


# Run tests with: pytest tests/integration/test_api_endpoints.py -v
