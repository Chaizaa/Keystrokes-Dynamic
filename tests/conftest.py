"""
Pytest configuration and fixtures for Keystrokes-Dynamic tests

Provides shared fixtures for:
- Flask app with test configuration
- Test database setup/teardown
- Service instances
- Sample test data
"""
import os
import sys
import tempfile
import pytest
from werkzeug.security import generate_password_hash

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from app import create_app
from app.models import db, User, KeystrokeVector, LoginAttempt
from app.services import AuthService, BiometricService


@pytest.fixture(scope='session')
def app():
    """
    Create Flask app with test configuration
    Uses in-memory SQLite database for faster tests
    """
    # Use in-memory database to avoid Windows file locking issues
    test_config = {
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,  # Disable CSRF for tests
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',  # In-memory database
        'SECRET_KEY': 'test-secret-key-for-testing-only',
        'RATELIMIT_ENABLED': False,  # Disable rate limiting for tests
    }
    
    app = create_app(test_config)
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture(scope='function')
def client(app):
    """
    Create Flask test client for making requests
    """
    return app.test_client()


@pytest.fixture(scope='function')
def runner(app):
    """
    Create Flask CLI test runner
    """
    return app.test_cli_runner()


@pytest.fixture(scope='function')
def app_context(app):
    """
    Provide application context for tests
    """
    with app.app_context():
        yield app


@pytest.fixture(scope='function')
def db_session(app):
    """
    Provide clean database session for each test
    Automatically rolls back changes after test
    """
    with app.app_context():
        # Clear all tables
        db.session.remove()
        db.drop_all()
        db.create_all()
        
        yield db.session
        
        # Rollback and clean up
        db.session.rollback()
        db.session.remove()


@pytest.fixture(scope='function')
def auth_service(app_context):
    """
    Provide AuthService instance for testing
    """
    return AuthService()


@pytest.fixture(scope='function')
def biometric_service(app_context):
    """
    Provide BiometricService instance for testing
    """
    return BiometricService()


@pytest.fixture(scope='function')
def sample_user(db_session):
    """
    Create a sample user for testing
    Returns User model instance
    """
    user = User(
        username='testuser',
        password_hash=generate_password_hash('TestPass123!')
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture(scope='function')
def sample_keystroke_features():
    """
    Provide sample keystroke features for testing
    Simulates a valid keystroke capture
    """
    return {
        'username': 'testuser',
        'H_vector': [0.1, 0.2, 0.15, 0.18, 0.12, 0.16, 0.14, 0.13],
        'DD_vector': [0.08, 0.09, 0.07, 0.085, 0.078, 0.082, 0.076, 0.081],
        'UD_vector': [0.18, 0.19, 0.17, 0.185, 0.175, 0.182, 0.176, 0.183],
        'data_type': 'enrollment',
        'quality_score': 0.85,
        'quality_label': 'Good'
    }


@pytest.fixture(scope='function')
def sample_enrollment_data():
    """
    Provide sample enrollment data for verification testing
    Simulates 10 training samples
    """
    base_h = [0.1, 0.2, 0.15, 0.18, 0.12, 0.16, 0.14, 0.13]
    base_dd = [0.08, 0.09, 0.07, 0.085, 0.078, 0.082, 0.076, 0.081]
    base_ud = [0.18, 0.19, 0.17, 0.185, 0.175, 0.182, 0.176, 0.183]
    
    samples = []
    for i in range(10):
        # Add slight variations to simulate real samples
        variation = 0.01 * (i - 5)  # Vary from -0.05 to +0.05
        sample = {
            'username': 'testuser',
            'H_vector': [h + variation for h in base_h],
            'DD_vector': [dd + variation for dd in base_dd],
            'UD_vector': [ud + variation for ud in base_ud],
            'data_type': 'enrollment'
        }
        samples.append(sample)
    
    return samples


@pytest.fixture(scope='function')
def authenticated_client(client, sample_user, app):
    """
    Provide authenticated test client
    User is already logged in
    """
    with client:
        with client.session_transaction() as sess:
            sess['_user_id'] = str(sample_user.id)
            sess['username'] = sample_user.username
        yield client
