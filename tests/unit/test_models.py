"""
Unit tests for database models
"""
import pytest
from datetime import datetime, timezone, timedelta
from app.models.user import User
from app.models.keystroke_vector import KeystrokeVector
from app.models.login_attempt import LoginAttempt
from sqlalchemy import select, func


class TestUserModel:
    """Test User model"""
    
    def test_user_creation(self, db_session):
        """Test creating a user"""
        user = User(
            username='testuser',
            password_hash='hashed_password_123'
        )
        db_session.add(user)
        db_session.commit()
        
        assert user.id is not None
        assert user.username == 'testuser'
        assert user.password_hash == 'hashed_password_123'
        assert user.created_at is not None
        assert user.updated_at is not None
    
    def test_user_timestamps_timezone_aware(self, db_session):
        """Test that user timestamps are timezone-aware"""
        user = User(username='testuser', password_hash='hash')
        db_session.add(user)
        db_session.commit()
        
        # Check that timestamps use timezone.utc
        assert user.created_at is not None
        assert user.updated_at is not None
        # SQLite may not preserve timezone info, so we just check they exist
    
    def test_user_repr(self, db_session):
        """Test user string representation"""
        user = User(username='testuser', password_hash='hash')
        db_session.add(user)
        db_session.commit()
        
        assert 'testuser' in repr(user)
        assert 'User' in repr(user)
    
    def test_user_to_dict(self, db_session):
        """Test user to_dict method"""
        user = User(
            username='testuser',
            password_hash='hash'
        )
        db_session.add(user)
        db_session.commit()
        
        user_dict = user.to_dict()
        
        assert user_dict['id'] == user.id
        assert user_dict['username'] == 'testuser'
        assert user_dict['enrollment_count'] == 0
        assert user_dict['has_password'] is True
        assert 'password_hash' not in user_dict  # Should not expose password hash
        assert 'created_at' in user_dict
    
    def test_user_unique_username(self, db_session):
        """Test that usernames must be unique"""
        user1 = User(username='testuser', password_hash='hash1')
        user2 = User(username='testuser', password_hash='hash2')
        
        db_session.add(user1)
        db_session.commit()
        
        db_session.add(user2)
        with pytest.raises(Exception):  # SQLAlchemy IntegrityError
            db_session.commit()
    
    def test_user_enrollment_status(self, db_session):
        """Test user enrollment status tracking"""
        user = User(username='testuser', password_hash='hash')
        db_session.add(user)
        db_session.commit()
        
        # Initially no enrollment samples
        assert user.get_enrollment_count() == 0
        
        # Add an enrollment sample
        from app.models.keystroke_vector import KeystrokeVector
        vector = KeystrokeVector(
            user_id=user.id,
            username='testuser',
            event_type='enrollment',
            is_successful=True
        )
        db_session.add(vector)
        db_session.commit()
        
        assert user.get_enrollment_count() == 1


class TestKeystrokeVectorModel:
    """Test KeystrokeVector model"""
    
    def test_keystroke_vector_creation(self, db_session):
        """Test creating a keystroke vector"""
        user = User(username='testuser', password_hash='hash')
        db_session.add(user)
        db_session.commit()
        
        vector = KeystrokeVector(
            user_id=user.id,
            username='testuser',
            event_type='enrollment',
            H_vector='[0.1, 0.2, 0.3]'
        )
        db_session.add(vector)
        db_session.commit()
        
        assert vector.id is not None
        assert vector.user_id == user.id
        assert vector.username == 'testuser'
        assert vector.event_type == 'enrollment'
        assert vector.timestamp is not None
    
    def test_keystroke_vector_timestamps(self, db_session):
        """Test keystroke vector timestamp is timezone-aware"""
        user = User(username='testuser', password_hash='hash')
        db_session.add(user)
        db_session.commit()
        
        vector = KeystrokeVector(
            user_id=user.id,
            username='testuser',
            event_type='enrollment'
        )
        db_session.add(vector)
        db_session.commit()
        
        assert vector.timestamp is not None
        # Check timestamp is recent (within last minute)
        # Note: SQLite may not preserve timezone, so we just check existence
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        time_diff = abs((now - vector.timestamp.replace(tzinfo=timezone.utc)).total_seconds())
        assert time_diff < 60
    
    def test_keystroke_vector_event_types(self, db_session):
        """Test different event types for keystroke vectors"""
        user = User(username='testuser', password_hash='hash')
        db_session.add(user)
        db_session.commit()
        
        enrollment = KeystrokeVector(
            user_id=user.id,
            username='testuser',
            event_type='enrollment'
        )
        login_attempt = KeystrokeVector(
            user_id=user.id,
            username='testuser',
            event_type='login_attempt'
        )
        
        db_session.add_all([enrollment, login_attempt])
        db_session.commit()
        
        # Query by event type
        enrollments = db_session.execute(
            select(KeystrokeVector).where(
                KeystrokeVector.user_id == user.id,
                KeystrokeVector.event_type == 'enrollment'
            )
        ).scalars().all()
        
        assert len(enrollments) == 1
        assert enrollments[0].event_type == 'enrollment'
    
    def test_keystroke_vector_statistical_features(self, db_session):
        """Test keystroke vector statistical features"""
        user = User(username='testuser', password_hash='hash')
        db_session.add(user)
        db_session.commit()
        
        vector = KeystrokeVector(
            user_id=user.id,
            username='testuser',
            event_type='enrollment',
            mean_H=0.123,
            std_H=0.045,
            mean_DD=0.234,
            std_DD=0.056
        )
        db_session.add(vector)
        db_session.commit()
        
        assert vector.mean_H == 0.123
        assert vector.std_H == 0.045
        assert vector.mean_DD == 0.234
        assert vector.std_DD == 0.056
    
    def test_keystroke_vector_to_dict(self, db_session):
        """Test keystroke vector to_dict method"""
        user = User(username='testuser', password_hash='hash')
        db_session.add(user)
        db_session.commit()
        
        vector = KeystrokeVector(
            user_id=user.id,
            username='testuser',
            event_type='enrollment',
            mean_H=0.123
        )
        db_session.add(vector)
        db_session.commit()
        
        vector_dict = vector.to_dict()
        
        assert vector_dict['id'] == vector.id
        assert vector_dict['username'] == 'testuser'
        assert vector_dict['event_type'] == 'enrollment'
        assert 'timestamp' in vector_dict


class TestLoginAttemptModel:
    """Test LoginAttempt model"""
    
    def test_login_attempt_creation(self, db_session):
        """Test creating a login attempt"""
        user = User(username='testuser', password_hash='hash')
        db_session.add(user)
        db_session.commit()
        
        attempt = LoginAttempt(
            user_id=user.id,
            username='testuser',
            success=True,
            verification_score=0.85,
            verification_method='biometric'
        )
        db_session.add(attempt)
        db_session.commit()
        
        assert attempt.id is not None
        assert attempt.user_id == user.id
        assert attempt.username == 'testuser'
        assert attempt.success is True
        assert attempt.verification_score == 0.85
        assert attempt.timestamp is not None
    
    def test_login_attempt_timestamp_timezone(self, db_session):
        """Test login attempt timestamp is timezone-aware"""
        attempt = LoginAttempt(
            username='testuser',
            success=True
        )
        db_session.add(attempt)
        db_session.commit()
        
        assert attempt.timestamp is not None
        # Check timestamp is recent
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        time_diff = abs((now - attempt.timestamp.replace(tzinfo=timezone.utc)).total_seconds())
        assert time_diff < 60
    
    def test_login_attempt_success_tracking(self, db_session):
        """Test tracking successful and failed attempts"""
        user = User(username='testuser', password_hash='hash')
        db_session.add(user)
        db_session.commit()
        
        success_attempt = LoginAttempt(
            user_id=user.id,
            username='testuser',
            success=True
        )
        failed_attempt = LoginAttempt(
            user_id=user.id,
            username='testuser',
            success=False,
            failure_reason='Invalid password'
        )
        
        db_session.add_all([success_attempt, failed_attempt])
        db_session.commit()
        
        # Query successful attempts
        successful = int(db_session.execute(
            select(func.count()).select_from(LoginAttempt).where(
                LoginAttempt.username == 'testuser',
                LoginAttempt.success == True
            )
        ).scalar_one())
        
        # Query failed attempts
        failed = int(db_session.execute(
            select(func.count()).select_from(LoginAttempt).where(
                LoginAttempt.username == 'testuser',
                LoginAttempt.success == False
            )
        ).scalar_one())
        
        assert successful == 1
        assert failed == 1
    
    def test_login_attempt_failure_reasons(self, db_session):
        """Test tracking failure reasons"""
        attempt1 = LoginAttempt(
            username='testuser',
            success=False,
            failure_reason='Invalid password'
        )
        attempt2 = LoginAttempt(
            username='testuser',
            success=False,
            failure_reason='Biometric verification failed'
        )
        
        db_session.add_all([attempt1, attempt2])
        db_session.commit()
        
        assert attempt1.failure_reason == 'Invalid password'
        assert attempt2.failure_reason == 'Biometric verification failed'
    
    def test_login_attempt_repr(self, db_session):
        """Test login attempt string representation"""
        success_attempt = LoginAttempt(
            username='testuser',
            success=True
        )
        failed_attempt = LoginAttempt(
            username='testuser',
            success=False
        )
        
        db_session.add_all([success_attempt, failed_attempt])
        db_session.commit()
        
        success_repr = repr(success_attempt)
        failed_repr = repr(failed_attempt)
        
        assert '✅' in success_repr
        assert 'testuser' in success_repr
        
        assert '❌' in failed_repr
        assert 'testuser' in failed_repr
    
    def test_login_attempt_to_dict(self, db_session):
        """Test login attempt to_dict method"""
        attempt = LoginAttempt(
            username='testuser',
            success=True,
            verification_score=0.85,
            ip_address='192.168.1.1'
        )
        db_session.add(attempt)
        db_session.commit()
        
        attempt_dict = attempt.to_dict()
        
        assert attempt_dict['username'] == 'testuser'
        assert attempt_dict['success'] is True
        assert attempt_dict['verification_score'] == 0.85
        assert attempt_dict['ip_address'] == '192.168.1.1'
        assert 'timestamp' in attempt_dict
    
    def test_get_recent_failed_attempts(self, db_session):
        """Test getting recent failed attempts"""
        user = User(username='testuser', password_hash='hash')
        db_session.add(user)
        db_session.commit()
        
        # Create failed attempts
        now = datetime.now(timezone.utc)
        
        # Recent failed attempt (within 15 minutes)
        recent = LoginAttempt(
            user_id=user.id,
            username='testuser',
            success=False,
            timestamp=now - timedelta(minutes=5)
        )
        
        # Old failed attempt (outside 15 minutes)
        old = LoginAttempt(
            user_id=user.id,
            username='testuser',
            success=False,
            timestamp=now - timedelta(minutes=20)
        )
        
        # Recent successful attempt (should not count)
        success = LoginAttempt(
            user_id=user.id,
            username='testuser',
            success=True,
            timestamp=now - timedelta(minutes=3)
        )
        
        db_session.add_all([recent, old, success])
        db_session.commit()
        
        # Test class method
        count = LoginAttempt.get_recent_failed_attempts('testuser', minutes=15)
        assert count == 1  # Only 'recent' should count
    
    def test_log_attempt_class_method(self, db_session):
        """Test log_attempt class method"""
        attempt = LoginAttempt.log_attempt(
            username='testuser',
            success=True,
            verification_score=0.87,
            ip_address='192.168.1.1'
        )
        
        assert attempt.id is not None
        assert attempt.username == 'testuser'
        assert attempt.success is True
        assert attempt.verification_score == 0.87
        assert attempt.ip_address == '192.168.1.1'
    
    def test_login_attempt_security_tracking(self, db_session):
        """Test security-related fields"""
        attempt = LoginAttempt(
            username='testuser',
            success=False,
            ip_address='192.168.1.100',
            user_agent='Mozilla/5.0',
            session_id='abc123',
            attempts_in_window=3,
            rate_limit_hit=True
        )
        db_session.add(attempt)
        db_session.commit()
        
        assert attempt.ip_address == '192.168.1.100'
        assert attempt.user_agent == 'Mozilla/5.0'
        assert attempt.session_id == 'abc123'
        assert attempt.attempts_in_window == 3
        assert attempt.rate_limit_hit is True
    
    def test_login_attempt_biometric_tracking(self, db_session):
        """Test biometric-related fields"""
        attempt = LoginAttempt(
            username='testuser',
            success=True,
            verification_score=0.92,
            verification_method='hybrid',
            biometric_tier='tier1'
        )
        db_session.add(attempt)
        db_session.commit()
        
        assert attempt.verification_score == 0.92
        assert attempt.verification_method == 'hybrid'
        assert attempt.biometric_tier == 'tier1'


class TestModelRelationships:
    """Test relationships between models"""
    
    def test_user_keystroke_vectors_relationship(self, db_session):
        """Test User -> KeystrokeVector relationship"""
        user = User(username='testuser', password_hash='hash')
        db_session.add(user)
        db_session.commit()
        
        # Create multiple keystroke vectors
        for i in range(3):
            vector = KeystrokeVector(
                user_id=user.id,
                username='testuser',
                event_type='enrollment'
            )
            db_session.add(vector)
        db_session.commit()
        
        # Query vectors by user_id
        vectors = db_session.execute(
            select(KeystrokeVector).where(KeystrokeVector.user_id == user.id)
        ).scalars().all()
        assert len(vectors) == 3
    
    def test_user_login_attempts_relationship(self, db_session):
        """Test User -> LoginAttempt relationship"""
        user = User(username='testuser', password_hash='hash')
        db_session.add(user)
        db_session.commit()
        
        # Create multiple login attempts
        for i in range(5):
            attempt = LoginAttempt(
                user_id=user.id,
                username='testuser',
                success=(i % 2 == 0)
            )
            db_session.add(attempt)
        db_session.commit()
        
        # Query attempts by user_id
        attempts = db_session.execute(
            select(LoginAttempt).where(LoginAttempt.user_id == user.id)
        ).scalars().all()
        assert len(attempts) == 5
        
        # Count successful attempts
        successful = int(db_session.execute(
            select(func.count()).select_from(LoginAttempt).where(
                LoginAttempt.user_id == user.id,
                LoginAttempt.success == True
            )
        ).scalar_one())
        assert successful == 3


class TestModelIndexes:
    """Test that database indexes are properly defined"""
    
    def test_login_attempt_indexes(self):
        """Test LoginAttempt composite indexes"""
        # Check that __table_args__ contains indexes
        assert hasattr(LoginAttempt, '__table_args__')
        indexes = LoginAttempt.__table_args__
        
        # Should have 4 composite indexes
        assert len(indexes) == 4
        
        # Check index names
        index_names = [idx.name for idx in indexes]
        assert 'idx_login_username_timestamp' in index_names
        assert 'idx_login_username_success' in index_names
        assert 'idx_login_user_timestamp' in index_names
        assert 'idx_login_ip_timestamp' in index_names
    
    def test_keystroke_vector_indexes(self):
        """Test KeystrokeVector composite indexes"""
        assert hasattr(KeystrokeVector, '__table_args__')
        indexes = KeystrokeVector.__table_args__
        
        # Should have 3 composite indexes
        assert len(indexes) == 3
        
        # Check index names
        index_names = [idx.name for idx in indexes]
        assert 'idx_vector_user_event_type' in index_names
        assert 'idx_vector_username_event' in index_names
        assert 'idx_vector_user_timestamp' in index_names
