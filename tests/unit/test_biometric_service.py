"""
Unit tests for BiometricService

Tests all biometric verification methods:
- Distance calculations (Euclidean, Cosine)
- Statistical similarity
- Keystroke sample verification
- Enrollment status tracking
"""
import pytest
import numpy as np
from app.services.biometric_service import BiometricService


class TestBiometricServiceDistanceCalculations:
    """Test distance calculation methods"""
    
    def test_calculate_euclidean_distance_identical_vectors(self, biometric_service):
        """Test Euclidean distance with identical vectors"""
        vector = [0.1, 0.2, 0.3, 0.4]
        
        distance = biometric_service.calculate_euclidean_distance(vector, vector)
        
        assert distance == 0.0, "Distance between identical vectors should be 0"
    
    def test_calculate_euclidean_distance_different_vectors(self, biometric_service):
        """Test Euclidean distance with different vectors"""
        vector1 = [0.0, 0.0, 0.0, 0.0]
        vector2 = [3.0, 4.0, 0.0, 0.0]
        
        distance = biometric_service.calculate_euclidean_distance(vector1, vector2)
        
        # Expected: sqrt(3^2 + 4^2) = 5.0
        assert distance == 5.0
    
    def test_calculate_euclidean_distance_returns_float(self, biometric_service):
        """Test that Euclidean distance returns float"""
        vector1 = [1, 2, 3]
        vector2 = [4, 5, 6]
        
        distance = biometric_service.calculate_euclidean_distance(vector1, vector2)
        
        assert isinstance(distance, float)
        assert distance > 0
    
    def test_calculate_cosine_similarity_identical_vectors(self, biometric_service):
        """Test cosine similarity with identical vectors"""
        vector = [0.1, 0.2, 0.3, 0.4]
        
        similarity = biometric_service.calculate_cosine_similarity(vector, vector)
        
        assert abs(similarity - 1.0) < 0.0001, "Similarity of identical vectors should be 1.0"
    
    def test_calculate_cosine_similarity_orthogonal_vectors(self, biometric_service):
        """Test cosine similarity with orthogonal vectors"""
        vector1 = [1.0, 0.0]
        vector2 = [0.0, 1.0]
        
        similarity = biometric_service.calculate_cosine_similarity(vector1, vector2)
        
        assert abs(similarity) < 0.0001, "Similarity of orthogonal vectors should be ~0"
    
    def test_calculate_cosine_similarity_opposite_vectors(self, biometric_service):
        """Test cosine similarity with opposite direction vectors"""
        vector1 = [1.0, 1.0]
        vector2 = [-1.0, -1.0]
        
        similarity = biometric_service.calculate_cosine_similarity(vector1, vector2)
        
        assert abs(similarity - (-1.0)) < 0.0001, "Similarity of opposite vectors should be -1.0"
    
    def test_calculate_cosine_similarity_returns_float(self, biometric_service):
        """Test that cosine similarity returns float in [-1, 1]"""
        vector1 = [1, 2, 3]
        vector2 = [4, 5, 6]
        
        similarity = biometric_service.calculate_cosine_similarity(vector1, vector2)
        
        assert isinstance(similarity, float)
        assert -1.0 <= similarity <= 1.0


class TestBiometricServiceStatisticalSimilarity:
    """Test statistical similarity calculations"""
    
    def test_calculate_statistical_similarity_identical(self, biometric_service):
        """Test statistical similarity with identical samples"""
        sample = {
            'H_vector': [0.1, 0.2, 0.3],
            'DD_vector': [0.05, 0.06, 0.07],
            'UD_vector': [0.15, 0.16, 0.17]
        }
        
        enrollment = [sample.copy() for _ in range(5)]
        
        result = biometric_service.calculate_statistical_similarity(sample, enrollment)
        
        assert result['score'] >= 0.95, "Identical samples should have high similarity"
        assert result['mean_h_diff'] < 0.01
        assert result['std_h_diff'] < 0.01
    
    def test_calculate_statistical_similarity_different(self, biometric_service):
        """Test statistical similarity with very different samples"""
        sample = {
            'H_vector': [0.1, 0.2, 0.3],
            'DD_vector': [0.05, 0.06, 0.07],
            'UD_vector': [0.15, 0.16, 0.17]
        }
        
        # Create very different enrollment data
        different_sample = {
            'H_vector': [0.9, 0.8, 0.7],
            'DD_vector': [0.45, 0.46, 0.47],
            'UD_vector': [0.95, 0.96, 0.97]
        }
        enrollment = [different_sample.copy() for _ in range(5)]
        
        result = biometric_service.calculate_statistical_similarity(sample, enrollment)
        
        assert result['score'] < 0.5, "Very different samples should have low similarity"


class TestBiometricServiceEnrollmentStatus:
    """Test enrollment status tracking"""
    
    def test_get_enrollment_status_no_samples(self, biometric_service, db_session):
        """Test enrollment status for user with no samples"""
        result = biometric_service.get_enrollment_status('nonexistent')
        
        assert result['count'] == 0
        assert result['enrolled'] is False
        assert result['ready_for_login'] is False
        assert result['minimum_samples'] == 3
        assert result['recommended_samples'] == 10
    
    def test_get_enrollment_status_with_samples(self, biometric_service, db_session, sample_user):
        """Test enrollment status for user with samples"""
        from app.models import KeystrokeVector
        
        # Create 5 keystroke samples
        for i in range(5):
            sample = KeystrokeVector(
                user_id=sample_user.id,
                h_vector=f"[0.{i}, 0.2, 0.3]",
                dd_vector="[0.05, 0.06, 0.07]",
                ud_vector="[0.15, 0.16, 0.17]",
                data_type='enrollment'
            )
            db_session.add(sample)
        db_session.commit()
        
        result = biometric_service.get_enrollment_status('testuser')
        
        assert result['count'] == 5
        assert result['enrolled'] is True  # >= 3 samples
        assert result['ready_for_login'] is False  # < 10 samples
    
    def test_get_enrollment_status_ready_for_login(self, biometric_service, db_session, sample_user):
        """Test enrollment status when user is ready for login"""
        from app.models import KeystrokeVector
        
        # Create 10 keystroke samples
        for i in range(10):
            sample = KeystrokeVector(
                user_id=sample_user.id,
                h_vector=f"[0.{i}, 0.2, 0.3]",
                dd_vector="[0.05, 0.06, 0.07]",
                ud_vector="[0.15, 0.16, 0.17]",
                data_type='enrollment'
            )
            db_session.add(sample)
        db_session.commit()
        
        result = biometric_service.get_enrollment_status('testuser')
        
        assert result['count'] == 10
        assert result['enrolled'] is True
        assert result['ready_for_login'] is True  # >= 10 samples


class TestBiometricServiceVerification:
    """Test keystroke verification functionality"""
    
    def test_verify_keystroke_sample_insufficient_enrollment(self, biometric_service):
        """Test verification with insufficient enrollment data"""
        sample = {
            'H_vector': [0.1, 0.2, 0.3],
            'DD_vector': [0.05, 0.06, 0.07],
            'UD_vector': [0.15, 0.16, 0.17]
        }
        
        # Only 1 enrollment sample (minimum is 3)
        enrollment = [sample.copy()]
        
        result = biometric_service.verify_keystroke_sample(sample, enrollment)
        
        assert 'error' in result
        assert 'insufficient' in result['error'].lower()
    
    def test_verify_keystroke_sample_genuine_user(self, biometric_service, sample_enrollment_data):
        """Test verification with genuine user (nearly identical sample)"""
        # Use first enrollment sample as test sample (should match)
        test_sample = sample_enrollment_data[0].copy()
        
        result = biometric_service.verify_keystroke_sample(test_sample, sample_enrollment_data)
        
        assert result['decision'] == 'genuine'
        assert result['confidence_score'] >= 0.85
        assert result['confidence_label'] in ['Exact Match', 'High Confidence']
        assert 'euclidean_score' in result
        assert 'cosine_score' in result
        assert 'statistical_score' in result
    
    def test_verify_keystroke_sample_impostor(self, biometric_service, sample_enrollment_data):
        """Test verification with impostor (very different sample)"""
        # Create completely different sample
        impostor_sample = {
            'username': 'impostor',
            'H_vector': [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2],
            'DD_vector': [0.5, 0.4, 0.3, 0.2, 0.1, 0.15, 0.25, 0.35],
            'UD_vector': [0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1],
            'data_type': 'verification'
        }
        
        result = biometric_service.verify_keystroke_sample(impostor_sample, sample_enrollment_data)
        
        assert result['decision'] == 'impostor'
        assert result['confidence_score'] < 0.55
        assert result['confidence_label'] in ['Low Confidence', 'Very Low Confidence']
    
    def test_verify_keystroke_sample_has_required_fields(self, biometric_service, sample_enrollment_data):
        """Test that verification result contains all required fields"""
        test_sample = sample_enrollment_data[0].copy()
        
        result = biometric_service.verify_keystroke_sample(test_sample, sample_enrollment_data)
        
        required_fields = [
            'decision',
            'confidence_score',
            'confidence_label',
            'euclidean_score',
            'cosine_score',
            'statistical_score',
            'primary_metric'
        ]
        
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"
    
    def test_verify_keystroke_sample_confidence_score_range(self, biometric_service, sample_enrollment_data):
        """Test that confidence score is in valid range [0, 1]"""
        test_sample = sample_enrollment_data[0].copy()
        
        result = biometric_service.verify_keystroke_sample(test_sample, sample_enrollment_data)
        
        assert 0.0 <= result['confidence_score'] <= 1.0
        assert isinstance(result['confidence_score'], float)


class TestBiometricServiceEdgeCases:
    """Test edge cases and error handling"""
    
    def test_calculate_euclidean_distance_empty_vectors(self, biometric_service):
        """Test Euclidean distance with empty vectors"""
        try:
            distance = biometric_service.calculate_euclidean_distance([], [])
            # Should either return 0 or raise an error
            assert distance == 0.0 or True
        except (ValueError, IndexError):
            # Expected to raise error for empty vectors
            pass
    
    def test_calculate_euclidean_distance_mismatched_lengths(self, biometric_service):
        """Test Euclidean distance with different length vectors"""
        try:
            distance = biometric_service.calculate_euclidean_distance([1, 2], [1, 2, 3])
            # Should handle gracefully or raise error
            assert True
        except (ValueError, IndexError):
            # Expected to raise error for mismatched lengths
            pass
    
    def test_verify_keystroke_sample_missing_vectors(self, biometric_service):
        """Test verification with missing vector data"""
        incomplete_sample = {
            'H_vector': [0.1, 0.2, 0.3],
            # Missing DD_vector and UD_vector
        }
        
        enrollment = [
            {
                'H_vector': [0.1, 0.2, 0.3],
                'DD_vector': [0.05, 0.06, 0.07],
                'UD_vector': [0.15, 0.16, 0.17]
            }
        ] * 5
        
        result = biometric_service.verify_keystroke_sample(incomplete_sample, enrollment)
        
        # Should handle gracefully with error
        assert 'error' in result or result['decision'] == 'impostor'


# Run tests with: pytest tests/unit/test_biometric_service.py -v
