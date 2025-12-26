"""
Biometric Service - Keystroke dynamics verification and analysis
Extracted from verifier.py for better separation of concerns
"""
import numpy as np
from scipy import stats
from typing import Dict, List, Tuple, Optional
from db import Database


class BiometricService:
    """
    Service class for biometric keystroke analysis and verification
    Handles all keystroke dynamics verification logic
    """
    
    def __init__(self):
        """Initialize biometric service with database connection"""
        self.db = Database()
        
        # Verification thresholds
        self.EXACT_MATCH_THRESHOLD = 0.95
        self.HIGH_CONFIDENCE_THRESHOLD = 0.85
        self.MEDIUM_CONFIDENCE_THRESHOLD = 0.70
        self.LOW_CONFIDENCE_THRESHOLD = 0.55
        
        # Minimum samples required
        self.MIN_SAMPLES_FOR_VERIFICATION = 3
        self.RECOMMENDED_SAMPLES = 10
    
    def calculate_euclidean_distance(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate Euclidean distance between two vectors
        
        Args:
            vec1: First feature vector
            vec2: Second feature vector
            
        Returns:
            Euclidean distance between vectors
        """
        if len(vec1) != len(vec2):
            raise ValueError("Vectors must have same length")
        
        vec1_array = np.array(vec1, dtype=float)
        vec2_array = np.array(vec2, dtype=float)
        
        return float(np.linalg.norm(vec1_array - vec2_array))
    
    def calculate_cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors
        
        Args:
            vec1: First feature vector
            vec2: Second feature vector
            
        Returns:
            Cosine similarity (0-1, higher is more similar)
        """
        if len(vec1) != len(vec2):
            raise ValueError("Vectors must have same length")
        
        vec1_array = np.array(vec1, dtype=float)
        vec2_array = np.array(vec2, dtype=float)
        
        dot_product = np.dot(vec1_array, vec2_array)
        norm1 = np.linalg.norm(vec1_array)
        norm2 = np.linalg.norm(vec2_array)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
    
    def calculate_statistical_similarity(self, sample_stats: Dict, template_stats: Dict) -> float:
        """
        Calculate similarity based on statistical features
        
        Args:
            sample_stats: Statistical features of login sample
            template_stats: Statistical features of enrollment template
            
        Returns:
            Statistical similarity score (0-1)
        """
        # Extract statistical features
        features = ['mean_H', 'std_H', 'mean_DD', 'std_DD', 'skew_H', 'kurtosis_H']
        
        similarities = []
        for feature in features:
            sample_val = sample_stats.get(feature, 0)
            template_val = template_stats.get(feature, 0)
            
            # Avoid division by zero
            if template_val == 0:
                similarity = 1.0 if sample_val == 0 else 0.0
            else:
                # Relative difference
                diff = abs(sample_val - template_val) / abs(template_val)
                similarity = max(0, 1 - diff)
            
            similarities.append(similarity)
        
        return float(np.mean(similarities))
    
    def verify_keystroke_sample(
        self,
        username: str,
        login_sample: Dict,
        use_statistical: bool = True
    ) -> Dict:
        """
        Verify a keystroke sample against enrolled templates
        
        Args:
            username: User to verify
            login_sample: Keystroke features from login attempt
            use_statistical: Whether to use statistical analysis
            
        Returns:
            Verification result with score and decision
        """
        # Get enrollment templates
        templates = self.db.get_enrollment_samples(username)
        
        if not templates or len(templates) < self.MIN_SAMPLES_FOR_VERIFICATION:
            return {
                'success': False,
                'verified': False,
                'score': 0.0,
                'reason': 'insufficient_samples',
                'message': f'Need at least {self.MIN_SAMPLES_FOR_VERIFICATION} enrollment samples'
            }
        
        # Extract feature vectors
        login_H = login_sample.get('H_vector', [])
        login_DD = login_sample.get('DD_vector', [])
        
        if not login_H or not login_DD:
            return {
                'success': False,
                'verified': False,
                'score': 0.0,
                'reason': 'invalid_features',
                'message': 'Missing required keystroke features'
            }
        
        # Calculate similarities against all templates
        similarities = []
        
        for template in templates:
            template_H = template.get('H_vector', [])
            template_DD = template.get('DD_vector', [])
            
            # Validate vector lengths before calculation
            if len(login_H) != len(template_H) or len(login_DD) != len(template_DD):
                print(f"[WARNING] Vector length mismatch: login_H={len(login_H)}, template_H={len(template_H)}, login_DD={len(login_DD)}, template_DD={len(template_DD)}")
                # Skip this template instead of throwing error
                continue
            
            # Euclidean distance similarity (inverted and normalized)
            h_distance = self.calculate_euclidean_distance(login_H, template_H)
            dd_distance = self.calculate_euclidean_distance(login_DD, template_DD)
            
            # Normalize distances to similarity (0-1)
            h_sim = 1 / (1 + h_distance)
            dd_sim = 1 / (1 + dd_distance)
            
            # Cosine similarity
            h_cosine = self.calculate_cosine_similarity(login_H, template_H)
            dd_cosine = self.calculate_cosine_similarity(login_DD, template_DD)
            
            # Combined similarity
            vector_similarity = (h_sim + dd_sim + h_cosine + dd_cosine) / 4
            
            # Add statistical similarity if enabled
            if use_statistical:
                stat_sim = self.calculate_statistical_similarity(login_sample, template)
                final_similarity = (vector_similarity * 0.7 + stat_sim * 0.3)
            else:
                final_similarity = vector_similarity
            
            similarities.append(final_similarity)
        
        # Check if we have any valid comparisons
        if not similarities:
            return {
                'success': False,
                'verified': False,
                'score': 0.0,
                'reason': 'password_length_mismatch',
                'message': 'Password length does not match enrollment. Please type the same password you registered with'
            }
        
        # Use maximum similarity (best match)
        max_similarity = max(similarities)
        avg_similarity = np.mean(similarities)
        
        # Determine verification result
        verified = max_similarity >= self.LOW_CONFIDENCE_THRESHOLD
        
        # Confidence level
        if max_similarity >= self.EXACT_MATCH_THRESHOLD:
            confidence = 'exact_match'
        elif max_similarity >= self.HIGH_CONFIDENCE_THRESHOLD:
            confidence = 'high'
        elif max_similarity >= self.MEDIUM_CONFIDENCE_THRESHOLD:
            confidence = 'medium'
        elif max_similarity >= self.LOW_CONFIDENCE_THRESHOLD:
            confidence = 'low'
        else:
            confidence = 'failed'
        
        return {
            'success': True,
            'verified': verified,
            'score': round(max_similarity, 4),
            'avg_score': round(avg_similarity, 4),
            'confidence': confidence,
            'templates_used': len(templates),
            'message': 'Biometric verification successful' if verified else 'Biometric verification failed'
        }
    
    def get_enrollment_status(self, username: str) -> Dict:
        """
        Get enrollment status for a user
        
        Args:
            username: User to check
            
        Returns:
            Enrollment status information
        """
        count = self.db.get_enrollment_count(username)
        
        return {
            'enrolled': count >= self.MIN_SAMPLES_FOR_VERIFICATION,
            'count': count,
            'required': self.MIN_SAMPLES_FOR_VERIFICATION,
            'recommended': self.RECOMMENDED_SAMPLES,
            'ready_for_login': count >= self.RECOMMENDED_SAMPLES
        }
