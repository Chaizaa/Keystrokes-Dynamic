import numpy as np
import json
from scipy.stats import skew, kurtosis

class Verifier:
    """
    Keystroke Biometric Verifier based on:
    K.S. Killourhy and R.A. Maxion. "Comparing Anomaly Detectors for
    Keystroke Biometrics," DSN 2009.
    
    Implements three anomaly detection methods:
    - Euclidean Distance (L2)
    - Manhattan Distance (L1)
    - Mahalanobis Distance (with covariance)
    """
    
    def __init__(self, method='euclidean', threshold=0.35):
        """
        Args:
            method: 'euclidean', 'manhattan', or 'mahalanobis'
            threshold: Decision threshold (lower = stricter)
                      Default 0.35 based on Killourhy & Maxion (2009) paper
        """
        self.method = method
        self.threshold = threshold
        self.MAX_BACKSPACE = 3
        self.OUTLIER_CAP = 1.0
    
    def _parse_vector(self, vector_data):
        """Parse vector from JSON string or list"""
        if isinstance(vector_data, str):
            try: 
                return np.array(json.loads(vector_data))
            except: 
                return np.array([])
        return np.array(vector_data)
    
    def extract_statistical_features(self, sample_dict):
        """
        Extract fixed-size statistical features from variable-length timing vectors.
        This allows users to use different password lengths!
        
        Args:
            sample_dict: Dict containing H_vector, DD_vector, UD_vector, UU_vector, DU_vector
        
        Returns:
            numpy array with 35 features (7 stats × 5 vectors):
            - mean, std, min, max, median, skewness, kurtosis for each vector
        
        Example:
            User A: password "test123" (7 chars) → 35 features
            User B: password "mypassword2024" (14 chars) → 35 features
            Both can be compared directly!
        """
        features = []
        
        # Process all 5 timing vectors
        vector_names = ['H_vector', 'DD_vector', 'UD_vector', 'UU_vector', 'DU_vector']
        
        for vector_name in vector_names:
            vec = self._parse_vector(sample_dict.get(vector_name, []))
            
            if len(vec) == 0:
                # Empty vector: add zeros for all 7 stats
                features.extend([0, 0, 0, 0, 0, 0, 0])
                continue
            
            # Calculate 7 statistical features per vector
            features.append(float(np.mean(vec)))       # 1. Mean (rata-rata timing)
            features.append(float(np.std(vec)))        # 2. Std deviation (variasi)
            features.append(float(np.min(vec)))        # 3. Minimum timing
            features.append(float(np.max(vec)))        # 4. Maximum timing
            features.append(float(np.median(vec)))     # 5. Median timing
            features.append(float(skew(vec)))          # 6. Skewness (asimetri distribusi)
            features.append(float(kurtosis(vec)))      # 7. Kurtosis (tail behavior)
        
        return np.array(features)  # Fixed size: 35 features
    
    def _extract_timing_vectors(self, samples):
        """
        Extract timing feature vectors from enrollment samples
        Returns: matrix where each row is a timing vector
        
        Field mapping:
        - H_vector (from process_web_events) = hold times
        - DD_vector (from process_web_events) = flight times (down-down)
        
        Also supports legacy field names (hold_times, flight_times) for compatibility.
        """
        vectors = []
        vector_lengths = []
        
        for sample in samples:
            # Try new field names first (H_vector, DD_vector), fallback to legacy names
            hold_times = self._parse_vector(
                sample.get('H_vector') or sample.get('hold_times', [])
            )
            flight_times = self._parse_vector(
                sample.get('DD_vector') or sample.get('flight_times', [])
            )
            
            if len(hold_times) == 0 and len(flight_times) == 0:
                continue
            
            # Combine into single feature vector
            feature_vector = np.concatenate([hold_times, flight_times])
            vectors.append(feature_vector)
            vector_lengths.append(len(feature_vector))
        
        if len(vectors) == 0:
            return np.array([])
        
        # ===================================================================
        # FIX: Validate vector length consistency
        # ===================================================================
        if len(set(vector_lengths)) > 1:
            # Different vector lengths detected! Filter to most common length
            from collections import Counter
            length_counts = Counter(vector_lengths)
            most_common_length = length_counts.most_common(1)[0][0]
            
            # Keep only vectors with most common length
            consistent_vectors = [
                v for v, length in zip(vectors, vector_lengths) 
                if length == most_common_length
            ]
            
            print(f"[WARNING] Inconsistent vector lengths detected!")
            print(f"  - Length distribution: {dict(length_counts)}")
            print(f"  - Using {len(consistent_vectors)}/{len(vectors)} samples with length {most_common_length}")
            
            vectors = consistent_vectors
        
        if len(vectors) == 0:
            return np.array([])
        
        return np.array(vectors)
    
    def _train_euclidean(self, Y_train):
        """
        Train Euclidean detector: calculate mean vector
        Based on euclideanTrain() from evaluation-script.R
        """
        mean_vector = np.mean(Y_train, axis=0)
        return {'mean': mean_vector}
    
    def _score_euclidean(self, model, Y_score):
        """
        Score using Euclidean distance: squared L2 distance from mean
        Based on euclideanScore() from evaluation-script.R
        """
        n = Y_score.shape[0]
        mean_matrix = np.tile(model['mean'], (n, 1))
        scores = np.sum((Y_score - mean_matrix) ** 2, axis=1)
        return scores
    
    def _train_manhattan(self, Y_train):
        """
        Train Manhattan detector: calculate mean vector
        Based on manhattanTrain() from evaluation-script.R
        """
        mean_vector = np.mean(Y_train, axis=0)
        return {'mean': mean_vector}
    
    def _score_manhattan(self, model, Y_score):
        """
        Score using Manhattan distance: L1 distance from mean
        Based on manhattanScore() from evaluation-script.R
        """
        n = Y_score.shape[0]
        mean_matrix = np.tile(model['mean'], (n, 1))
        scores = np.sum(np.abs(Y_score - mean_matrix), axis=1)
        return scores
    
    def _train_mahalanobis(self, Y_train):
        """
        Train Mahalanobis detector: calculate mean and covariance inverse
        Based on mahalanobisTrain() from evaluation-script.R
        """
        mean_vector = np.mean(Y_train, axis=0)
        cov_matrix = np.cov(Y_train, rowvar=False)
        
        # Use pseudo-inverse for numerical stability
        try:
            cov_inv = np.linalg.pinv(cov_matrix)
        except:
            # Fallback to identity if inversion fails
            cov_inv = np.eye(cov_matrix.shape[0])
        
        return {'mean': mean_vector, 'cov_inv': cov_inv}
    
    def _score_mahalanobis(self, model, Y_score):
        """
        Score using Mahalanobis distance
        Based on mahalanobisScore() from evaluation-script.R
        """
        scores = []
        for y in Y_score:
            diff = y - model['mean']
            score = np.dot(np.dot(diff, model['cov_inv']), diff.T)
            scores.append(score)
        return np.array(scores)
    
    def verify_user(self, new_features, enrollment_samples):
        """
        Verify user identity using keystroke biometrics
        
        Args:
            new_features: Dict with timing data from new login attempt
            enrollment_samples: List of enrollment samples (training data)
        
        Returns:
            Dict with: result (bool), score (float), msg (str), method (str)
        """
        
        # 1. Check if enrollment data exists
        if not enrollment_samples or len(enrollment_samples) == 0:
            return {
                "result": False, 
                "score": 1.0,
                "msg": "❌ No enrollment data",
                "method": self.method
            }
        
        # 2. Check password hash (must match)
        stored_hash = enrollment_samples[0].get('password_hash', '')
        new_hash = new_features.get('password_hash', '')
        
        if new_hash != stored_hash:
            return {
                "result": False,
                "score": 1.0,
                "msg": "❌ Wrong password",
                "method": self.method
            }
        
        # 3. Extract timing vectors from enrollment (training data)
        Y_train = self._extract_timing_vectors(enrollment_samples)
        
        if len(Y_train) == 0:
            return {
                "result": False,
                "score": 1.0,
                "msg": "❌ No valid enrollment data (vector extraction failed)",
                "method": self.method
            }
        
        if Y_train.shape[0] < 3:
            return {
                "result": False,
                "score": 1.0,
                "msg": f"❌ Insufficient enrollment data ({Y_train.shape[0]} samples, need at least 3)",
                "method": self.method
            }
        
        # 4. Extract timing vector from new sample
        # Try new field names first (H_vector, DD_vector), fallback to legacy names
        new_hold = self._parse_vector(
            new_features.get('H_vector') or new_features.get('hold_times', [])
        )
        new_flight = self._parse_vector(
            new_features.get('DD_vector') or new_features.get('flight_times', [])
        )
        
        if len(new_hold) == 0 and len(new_flight) == 0:
            return {
                "result": False,
                "score": 1.0,
                "msg": "❌ No timing features in new sample",
                "method": self.method
            }
        
        new_vector = np.concatenate([new_hold, new_flight])
        Y_score = new_vector.reshape(1, -1)  # Shape: (1, n_features)
        
        # 5. Check feature dimension match
        if Y_score.shape[1] != Y_train.shape[1]:
            return {
                "result": False,
                "score": 1.0,
                "msg": f"❌ Feature dimension mismatch (expected {Y_train.shape[1]}, got {Y_score.shape[1]})",
                "method": self.method
            }
        
        # 6. Train detector and calculate score based on selected method
        try:
            if self.method == 'euclidean':
                model = self._train_euclidean(Y_train)
                raw_score = self._score_euclidean(model, Y_score)[0]
            elif self.method == 'manhattan':
                model = self._train_manhattan(Y_train)
                raw_score = self._score_manhattan(model, Y_score)[0]
            elif self.method == 'mahalanobis':
                model = self._train_mahalanobis(Y_train)
                raw_score = self._score_mahalanobis(model, Y_score)[0]
            else:
                return {
                    "result": False,
                    "score": 1.0,
                    "msg": f"❌ Unknown method: {self.method}",
                    "method": self.method
                }
        except Exception as e:
            return {
                "result": False,
                "score": 1.0,
                "msg": f"❌ Scoring error: {str(e)}",
                "method": self.method
            }
        
        # 7. Normalize score to [0, 1] range for consistent thresholding
        # Lower score = more similar to enrollment pattern = genuine user
        normalized_score = min(raw_score / 100.0, 1.0)  # Cap at 1.0
        
        # 8. Decision: Accept if score <= threshold
        is_genuine = (normalized_score <= self.threshold)
        
        result_msg = (
            f"✅ Genuine user (score: {normalized_score:.3f}, threshold: {self.threshold})" 
            if is_genuine else 
            f"❌ Impostor detected (score: {normalized_score:.3f} > threshold: {self.threshold})"
        )
        
        return {
            "result": is_genuine,
            "score": normalized_score,
            "raw_score": raw_score,
            "msg": result_msg,
            "method": self.method,
            "threshold": self.threshold,
            "n_enrollment": Y_train.shape[0]
        }