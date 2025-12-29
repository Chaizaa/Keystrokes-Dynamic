"""
Unit tests for AuthService

Tests all authentication-related methods:
- Username validation
- Password validation
- User creation
- Password verification
- Username availability checking
- Password changing
"""
import pytest
from flask import session
from app.services.auth_service import AuthService
from app.models import User
from sqlalchemy import select


class TestAuthServiceValidation:
    """Test validation methods"""
    
    def test_validate_username_valid(self, auth_service):
        """Test valid usernames pass validation"""
        valid_usernames = [
            'john_doe',
            'user123',
            'test-user',
            'abc',  # Minimum 3 chars
            'a' * 50,  # Maximum 50 chars
            'User_Name-123'
        ]
        
        for username in valid_usernames:
            result = auth_service.validate_username(username)
            assert result['valid'] is True, f"Failed for: {username}"
            assert 'message' in result
    
    def test_validate_username_invalid_length(self, auth_service):
        """Test usernames with invalid length"""
        invalid_usernames = [
            '',  # Empty
            'ab',  # Too short (< 3)
            'a' * 51,  # Too long (> 50)
        ]
        
        for username in invalid_usernames:
            result = auth_service.validate_username(username)
            assert result['valid'] is False, f"Should fail for: {username}"
            # Check message mentions length/empty/characters (different messages for different cases)
            assert any(word in result['message'].lower() for word in ['length', 'empty', 'characters'])
    
    def test_validate_username_invalid_characters(self, auth_service):
        """Test usernames with invalid characters"""
        invalid_usernames = [
            'user@name',  # @ not allowed
            'user name',  # Space not allowed
            'user#123',   # # not allowed
            'user.name',  # . not allowed
            'user!',      # ! not allowed
        ]
        
        for username in invalid_usernames:
            result = auth_service.validate_username(username)
            assert result['valid'] is False, f"Should fail for: {username}"
    
    def test_validate_password_valid(self, auth_service):
        """Test valid passwords pass validation"""
        valid_passwords = [
            'Pass1234',
            'Pass1',         # shorter passwords allowed (keystroke auth)
            'TestPassword!', # With special char
            'a' * 128,       # Maximum 128 chars
            'MyP@ssw0rd123'  # Mix of all
        ]
        
        for password in valid_passwords:
            result = auth_service.validate_password(password)
            assert result['valid'] is True, f"Failed for: {password}"
    
    def test_validate_password_invalid_length(self, auth_service):
        """Test passwords with invalid length"""
        invalid_passwords = [
            '',          # Empty
            'a' * 129,   # Too long (> 128)
        ]
        
        for password in invalid_passwords:
            result = auth_service.validate_password(password)
            assert result['valid'] is False, f"Should fail for: {password}"
            # Check message mentions length OR empty OR characters
            assert any(word in result['message'].lower() for word in ['length', 'characters', 'empty'])


class TestAuthServiceUserManagement:
    """Test user creation and management"""
    
    def test_create_user_success(self, auth_service, db_session):
        """Test successful user creation"""
        result = auth_service.create_user('newuser', 'NewPass123!')
        
        assert result['success'] is True
        assert 'user' in result
        assert result['user'].username == 'newuser'
        assert result['user'].password_hash is not None
        assert result['user'].password_hash != 'NewPass123!'  # Should be hashed
        
        # Verify user exists in database
        from app.models import db
        user = db.session.execute(select(User).where(User.username == 'newuser')).scalars().first()
        assert user is not None
        assert user.username == 'newuser'
    
    def test_create_user_invalid_username(self, auth_service, db_session):
        """Test user creation with invalid username"""
        result = auth_service.create_user('ab', 'ValidPass123!')  # Too short
        
        assert result['success'] is False
        assert 'message' in result
        assert 'username' in result['message'].lower()
    
    def test_create_user_invalid_password(self, auth_service, db_session):
        """Test user creation with invalid password (empty or too long)"""
        # Use empty password to trigger validation failure
        result = auth_service.create_user('validuser', '')
        
        assert result['success'] is False
        assert 'message' in result
        assert 'password' in result['message'].lower()
    
    def test_create_user_duplicate_username(self, auth_service, db_session, sample_user):
        """Test user creation with existing username"""
        result = auth_service.create_user('testuser', 'NewPass123!')  # testuser exists
        
        assert result['success'] is False
        assert 'already exists' in result['message'].lower()
    
    def test_check_username_availability_available(self, auth_service, db_session):
        """Test checking availability of non-existent username"""
        result = auth_service.check_username_availability('newuser')
        
        assert result['available'] is True
        assert result['exists'] is False
        assert 'available' in result['message'].lower()
    
    def test_check_username_availability_taken(self, auth_service, db_session, sample_user):
        """Test checking availability of existing username"""
        result = auth_service.check_username_availability('testuser')
        
        assert result['available'] is False
        assert result['exists'] is True
        assert 'taken' in result['message'].lower() or 'exists' in result['message'].lower()

    def test_check_username_availability_resumable(self, auth_service, db_session, monkeypatch):
        """When enrollment samples exist but user isn't created, mark as resumable and NOT available"""
        # Simulate enrollment samples present
        monkeypatch.setattr(auth_service.db, 'get_enrollment_count', lambda u: 5)
        result = auth_service.check_username_availability('partialuser')
        assert result['available'] is False
        assert result['exists'] is False
        assert result['reason'] == 'resumable'
        assert result['enrollment_count'] == 5
    
    def test_check_username_availability_invalid(self, auth_service):
        """Test checking availability with invalid username format"""
        result = auth_service.check_username_availability('ab')  # Too short
        
        assert result['available'] is False
        assert 'message' in result


class TestAuthServicePasswordVerification:
    """Test password verification methods"""
    
    def test_verify_password_bcrypt_correct(self, auth_service, db_session, sample_user):
        """Test verifying correct bcrypt password"""
        is_valid, user = auth_service.verify_password(sample_user.username, 'TestPass123!')
        
        assert is_valid is True
        assert user == sample_user
    
    def test_verify_password_bcrypt_incorrect(self, auth_service, db_session, sample_user):
        """Test verifying incorrect bcrypt password"""
        is_valid, user = auth_service.verify_password(sample_user.username, 'WrongPassword')
        
        assert is_valid is False
        assert user is None
    
    def test_verify_password_legacy_sha256(self, auth_service, db_session):
        """Test verifying legacy SHA-256 password"""
        import hashlib
        
        # Create user with legacy SHA-256 hash
        legacy_password = 'LegacyPass123'
        legacy_hash = hashlib.sha256(legacy_password.encode()).hexdigest()
        
        user = User(
            username='legacyuser',
            password_hash=legacy_hash
        )
        db_session.add(user)
        db_session.commit()
        
        # Legacy SHA-256 might not be supported (bcrypt only)
        # This test documents that behavior
        is_valid, returned_user = auth_service.verify_password(user.username, legacy_password)
        # If legacy support is removed, this will fail (expected)
        assert is_valid is False  # bcrypt-only mode
    
    def test_verify_password_legacy_incorrect(self, auth_service, db_session):
        """Test verifying incorrect legacy password"""
        import hashlib
        
        # Create user with legacy SHA-256 hash
        legacy_password = 'LegacyPass123'
        legacy_hash = hashlib.sha256(legacy_password.encode()).hexdigest()
        
        user = User(
            username='legacyuser2',
            password_hash=legacy_hash
        )
        db_session.add(user)
        db_session.commit()
        
        # Should fail with wrong password
        is_valid, returned_user = auth_service.verify_password(user.username, 'WrongPassword')
        assert is_valid is False
        assert returned_user is None


class TestAuthServicePasswordChange:
    """Test password changing functionality"""
    
    def test_change_password_success(self, auth_service, db_session, sample_user):
        """Test successful password change"""
        old_hash = sample_user.password_hash
        
        success, message = auth_service.change_password(sample_user.username, 'TestPass123!', 'NewPassword123!')
        
        assert success is True
        assert 'successfully' in message.lower() or 'changed' in message.lower()
        
        # Verify password was changed
        db_session.refresh(sample_user)
        assert sample_user.password_hash != old_hash
        
        # Verify new password works
        is_valid, user = auth_service.verify_password(sample_user.username, 'NewPassword123!')
        assert is_valid is True
        
        # Verify old password doesn't work
        is_valid_old, _ = auth_service.verify_password(sample_user.username, 'TestPass123!')
        assert is_valid_old is False
    
    def test_change_password_invalid(self, auth_service, db_session, sample_user):
        """Test password change with invalid new password"""
        original_hash = sample_user.password_hash
        
        # Try to change with an empty password (invalid)
        success, message = auth_service.change_password(sample_user.username, 'TestPass123!', '')
        
        assert success is False
        assert any(word in message.lower() for word in ['length', 'characters', 'must', 'empty'])
        
        # Verify password was NOT changed
        db_session.refresh(sample_user)
        assert sample_user.password_hash == original_hash


class TestAuthServiceSessionManagement:
    """Test session management methods"""
    
    def test_login_user_session(self, auth_service, sample_user, app):
        """Test creating user session"""
        with app.test_request_context():
            success = auth_service.login_user_session(sample_user)
            
            assert success is True
            assert session.get('username') == sample_user.username
            assert session.get('user_id') == sample_user.id
    
    def test_logout_user_session(self, auth_service, app):
        """Test terminating user session"""
        with app.test_request_context():
            success = auth_service.logout_user_session()
            
            assert success is True


# Run tests with: pytest tests/unit/test_auth_service.py -v
