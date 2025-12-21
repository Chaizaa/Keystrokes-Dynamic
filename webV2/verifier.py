import numpy as np
import json
from scipy.stats import skew, kurtosis, trim_mean

class Verifier:
    """
    Enhanced Keystroke Biometric Verifier based on:
    K.S. Killourhy and R.A. Maxion. "Comparing Anomaly Detectors for
    Keystroke Biometrics," DSN 2009.
    
    Implements multiple anomaly detection methods:
    - Baseline: Euclidean, Manhattan, Mahalanobis
    - Outlier-Robust: IQR, Z-Score, Isolation Forest
    - Robust Statistics: Trimmed Mean, Robust Covariance
    - Adaptive Threshold: Per-user threshold calculation
    """
    
    def __init__(self, method='euclidean', threshold=0.1, 
                 outlier_method='none', use_robust_stats=False, 
                 adaptive_threshold=False):
        """
        Args:
            method: 'euclidean', 'manhattan', or 'mahalanobis'
            threshold: Decision threshold (lower = stricter)
            outlier_method: 'none', 'iqr', 'zscore', 'iforest'
            use_robust_stats: Use trimmed mean instead of regular mean
            adaptive_threshold: Calculate threshold per-user
        """
        self.method = method
        self.threshold = threshold
        self.outlier_method = outlier_method
        self.use_robust_stats = use_robust_stats
        self.adaptive_threshold = adaptive_threshold
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
    
    # ===================================================================
    # OUTLIER DETECTION METHODS
    # ===================================================================
    
    def _remove_outliers_iqr(self, vectors):
        """
        Remove outlier samples using IQR (Interquartile Range) method
        
        Args:
            vectors: numpy array of shape (n_samples, n_features)
        
        Returns:
            Clean vectors with outliers removed
        """
        if len(vectors) < 3:
            return vectors
        
        # Calculate Q1, Q3, IQR per feature
        Q1 = np.percentile(vectors, 25, axis=0)
        Q3 = np.percentile(vectors, 75, axis=0)
        IQR = Q3 - Q1
        
        # Define outlier bounds
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        
        # Keep only samples within bounds (all features)
        mask = np.all((vectors >= lower_bound) & (vectors <= upper_bound), axis=1)
        clean_vectors = vectors[mask]
        
        n_removed = len(vectors) - len(clean_vectors)
        
        # Safety check: don't remove more than 50% of samples
        min_samples_required = max(3, len(vectors) // 2)
        if len(clean_vectors) < min_samples_required:
            print(f"[IQR Warning] Would remove too many samples ({len(vectors)} → {len(clean_vectors)}), keeping original data")
            return vectors
        
        if n_removed > 0:
            print(f"[IQR Outlier Removal] {len(vectors)} → {len(clean_vectors)} samples ({n_removed} outliers removed)")
        
        return clean_vectors if len(clean_vectors) > 0 else vectors
    
    def _remove_outliers_zscore(self, vectors, threshold=3.0):
        """
        Remove samples with Z-score > threshold (default 3.0 = 99.7% confidence)
        
        Args:
            vectors: numpy array of shape (n_samples, n_features)
            threshold: Z-score threshold (typically 2.5-3.0)
        
        Returns:
            Clean vectors with outliers removed
        """
        if len(vectors) < 3:
            return vectors
        
        # Calculate Z-scores per feature
        mean = np.mean(vectors, axis=0)
        std = np.std(vectors, axis=0)
        
        # Avoid division by zero
        std[std == 0] = 1.0
        
        z_scores = np.abs((vectors - mean) / std)
        
        # Keep samples where all features have Z-score < threshold
        mask = np.all(z_scores < threshold, axis=1)
        clean_vectors = vectors[mask]
        
        n_removed = len(vectors) - len(clean_vectors)
        if n_removed > 0:
            print(f"[Z-Score Outlier Removal] {len(vectors)} → {len(clean_vectors)} samples ({n_removed} outliers removed)")
        
        return clean_vectors if len(clean_vectors) > 0 else vectors
    
    def _remove_outliers_iforest(self, vectors):
        """
        Remove anomalous samples using Isolation Forest (ML-based)
        
        Args:
            vectors: numpy array of shape (n_samples, n_features)
        
        Returns:
            Clean vectors with anomalies removed
        """
        if len(vectors) < 5:
            return vectors
        
        try:
            from sklearn.ensemble import IsolationForest
            
            # contamination = expected proportion of outliers (10%)
            clf = IsolationForest(contamination=0.1, random_state=42, n_estimators=100)
            predictions = clf.fit_predict(vectors)
            
            # Keep inliers (prediction == 1)
            clean_vectors = vectors[predictions == 1]
            
            n_removed = len(vectors) - len(clean_vectors)
            if n_removed > 0:
                print(f"[Isolation Forest] {len(vectors)} → {len(clean_vectors)} samples ({n_removed} anomalies removed)")
            
            return clean_vectors if len(clean_vectors) > 0 else vectors
        
        except ImportError:
            print("[WARNING] scikit-learn not installed, skipping Isolation Forest")
            return vectors
    
    def _cap_outliers(self, vector, cap_percentile=95):
        """
        Cap extreme values to percentile threshold (per-feature outlier capping)
        
        Args:
            vector: numpy array (single feature vector)
            cap_percentile: Percentile to cap at (default 95%)
        
        Returns:
            Capped vector
        """
        if len(vector) == 0:
            return vector
        
        cap_value = np.percentile(vector, cap_percentile)
        capped = np.clip(vector, 0, cap_value)
        
        n_capped = np.sum(vector != capped)
        if n_capped > 0:
            print(f"[Outlier Capping] {n_capped} values capped at {cap_percentile}th percentile")
        
        return capped
    
    # ===================================================================
    # ROBUST STATISTICS METHODS
    # ===================================================================
    
    def _calculate_adaptive_threshold(self, Y_train, false_accept_rate=0.05):
        """
        Calculate adaptive threshold based on training score distribution
        
        Args:
            Y_train: Training vectors
            false_accept_rate: Desired FAR (default 5%)
        
        Returns:
            Adaptive threshold value
        """
        # Minimum sample check
        if len(Y_train) < 3:
            print(f"[Adaptive Threshold Warning] Only {len(Y_train)} samples, using fallback threshold")
            return 0.5  # Fallback threshold
        
        # Use more lenient FAR for small datasets
        if len(Y_train) < 20:
            false_accept_rate = 0.10  # 10% FAR for small datasets
            print(f"[Adaptive Threshold] Small dataset ({len(Y_train)} samples), using lenient FAR: 10%")
        
        # Train model on enrollment data
        if self.method == 'euclidean':
            model = self._train_euclidean(Y_train)
            train_scores = self._score_euclidean(model, Y_train)
        elif self.method == 'manhattan':
            model = self._train_manhattan(Y_train)
            train_scores = self._score_manhattan(model, Y_train)
        elif self.method == 'mahalanobis':
            model = self._train_mahalanobis(Y_train)
            train_scores = self._score_mahalanobis(model, Y_train)
        else:
            return self.threshold
        
        # Normalize scores
        normalized_scores = np.minimum(train_scores / 100.0, 1.0)
        
        # Set threshold at (1-FAR) percentile of genuine scores
        percentile = (1 - false_accept_rate) * 100
        adaptive_threshold = np.percentile(normalized_scores, percentile)
        
        # Ensure threshold is not zero or too small (would reject everything)
        if adaptive_threshold == 0.0:
            adaptive_threshold = np.max(normalized_scores) + 1e-6  # Slightly above max score
            print(f"[Adaptive Threshold] Adjusted zero threshold to {adaptive_threshold:.6f}")
        elif adaptive_threshold < 0.001 and len(Y_train) < 20:
            # For small datasets, ensure minimum threshold to avoid over-strict rejection
            adaptive_threshold = max(adaptive_threshold, 0.01)
            print(f"[Adaptive Threshold] Adjusted too-small threshold to {adaptive_threshold:.6f} (small dataset protection)")
        
        print(f"[Adaptive Threshold] Calculated: {adaptive_threshold:.4f} (FAR target: {false_accept_rate*100:.1f}%)")
        
        return adaptive_threshold
    
    def _train_euclidean(self, Y_train):
        """
        Train Euclidean detector: calculate mean vector
        Based on euclideanTrain() from evaluation-script.R
        """
        if self.use_robust_stats:
            # Use trimmed mean (10% trim from both ends)
            mean_vector = trim_mean(Y_train, proportiontocut=0.1, axis=0)
            print("[Robust Stats] Using trimmed mean (10% trim)")
        else:
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
        if self.use_robust_stats:
            # Use trimmed mean (10% trim from both ends)
            mean_vector = trim_mean(Y_train, proportiontocut=0.1, axis=0)
            print("[Robust Stats] Using trimmed mean (10% trim)")
        else:
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
        if self.use_robust_stats:
            # Use trimmed mean and robust covariance
            mean_vector = trim_mean(Y_train, proportiontocut=0.1, axis=0)
            
            # Check if dataset is large enough for MCD (needs n_samples >= n_features)
            n_samples, n_features = Y_train.shape
            if n_samples < n_features:
                print(f"[Robust Stats] Dataset too small for MCD ({n_samples} samples < {n_features} features), using regular covariance")
                cov_matrix = np.cov(Y_train, rowvar=False)
            else:
                try:
                    from sklearn.covariance import MinCovDet
                    import warnings
                    # Minimum Covariance Determinant (robust covariance estimator)
                    with warnings.catch_warnings():
                        warnings.filterwarnings('ignore', category=UserWarning)
                        warnings.filterwarnings('ignore', category=RuntimeWarning)
                        robust_cov = MinCovDet(random_state=42).fit(Y_train)
                    cov_matrix = robust_cov.covariance_
                    print("[Robust Stats] Using trimmed mean + robust covariance (MCD)")
                except (ImportError, Exception) as e:
                    print(f"[Robust Stats] MCD failed, using regular covariance")
                    cov_matrix = np.cov(Y_train, rowvar=False)
        else:
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
    
    # ===================================================================
    # COMPREHENSIVE VERIFICATION (ALL METHODS)
    # ===================================================================
    
    def verify_user_comprehensive(self, new_features, enrollment_samples):
        """
        Verify user using ALL methods and return detailed comparison
        
        Args:
            new_features: Dict with timing data from new login attempt
            enrollment_samples: List of enrollment samples (training data)
        
        Returns:
            Dict with results from all 9 methods + recommendation
        """
        
        # 1. Check if enrollment data exists
        if not enrollment_samples or len(enrollment_samples) == 0:
            return {
                "error": True,
                "msg": "❌ No enrollment data",
                "results": {}
            }
        
        # 2. Check password hash (must match)
        stored_hash = enrollment_samples[0].get('password_hash', '')
        new_hash = new_features.get('password_hash', '')
        
        if new_hash != stored_hash:
            return {
                "error": True,
                "msg": "❌ Wrong password",
                "results": {}
            }
        
        # 3. Extract timing vectors from enrollment (training data)
        Y_train_original = self._extract_timing_vectors(enrollment_samples)
        
        if len(Y_train_original) == 0:
            return {
                "error": True,
                "msg": "❌ No valid enrollment data (vector extraction failed)",
                "results": {}
            }
        
        if Y_train_original.shape[0] < 5:
            return {
                "error": True,
                "msg": f"❌ Insufficient enrollment data ({Y_train_original.shape[0]} samples, need at least 5 for comprehensive analysis)",
                "results": {}
            }
        
        # 4. Extract timing vector from new sample
        new_hold = self._parse_vector(
            new_features.get('H_vector') or new_features.get('hold_times', [])
        )
        new_flight = self._parse_vector(
            new_features.get('DD_vector') or new_features.get('flight_times', [])
        )
        
        if len(new_hold) == 0 and len(new_flight) == 0:
            return {
                "error": True,
                "msg": "❌ No timing features in new sample",
                "results": {}
            }
        
        new_vector = np.concatenate([new_hold, new_flight])
        Y_score = new_vector.reshape(1, -1)
        
        # 5. Check feature dimension match
        if Y_score.shape[1] != Y_train_original.shape[1]:
            return {
                "error": True,
                "msg": f"❌ Feature dimension mismatch (expected {Y_train_original.shape[1]}, got {Y_score.shape[1]})",
                "results": {}
            }
        
        # ===================================================================
        # RUN ALL 9 METHODS
        # ===================================================================
        
        results = {}
        
        print("\n" + "="*60)
        print("COMPREHENSIVE VERIFICATION ANALYSIS")
        print("="*60)
        
        # --- BASELINE METHODS ---
        print("\n📊 BASELINE METHODS:")
        
        # Euclidean
        results['euclidean'] = self._verify_single_method(
            'euclidean', Y_train_original, Y_score, use_robust=False, outlier_method='none'
        )
        
        # Manhattan
        results['manhattan'] = self._verify_single_method(
            'manhattan', Y_train_original, Y_score, use_robust=False, outlier_method='none'
        )
        
        # Mahalanobis (skip for very small datasets - unreliable)
        n_samples, n_features = Y_train_original.shape
        if n_samples < 20:
            print(f"  [Mahalanobis                   ] ⚠️ Skipped (dataset too small: {n_samples} samples < 20)")
            results['mahalanobis'] = {
                'result': True,  # Default to accept to not bias consensus
                'score': 0.0,
                'threshold': 0.0,
                'msg': 'Skipped (dataset too small for reliable covariance)',
                'n_samples_used': n_samples,
                'outlier_method': 'none',
                'use_robust_stats': False,
                'skipped': True
            }
        else:
            results['mahalanobis'] = self._verify_single_method(
                'mahalanobis', Y_train_original, Y_score, use_robust=False, outlier_method='none'
            )
        
        # --- OUTLIER-ROBUST METHODS ---
        print("\n🛡️ OUTLIER-ROBUST METHODS:")
        
        # Euclidean + IQR
        results['euclidean_iqr'] = self._verify_single_method(
            'euclidean', Y_train_original, Y_score, use_robust=False, outlier_method='iqr'
        )
        
        # Euclidean + Z-Score
        results['euclidean_zscore'] = self._verify_single_method(
            'euclidean', Y_train_original, Y_score, use_robust=False, outlier_method='zscore'
        )
        
        # Euclidean + Isolation Forest
        results['euclidean_iforest'] = self._verify_single_method(
            'euclidean', Y_train_original, Y_score, use_robust=False, outlier_method='iforest'
        )
        
        # --- ROBUST STATISTICS ---
        print("\n📈 ROBUST STATISTICS:")
        
        # Euclidean + Trimmed Mean
        results['euclidean_robust'] = self._verify_single_method(
            'euclidean', Y_train_original, Y_score, use_robust=True, outlier_method='none'
        )
        
        # Manhattan + Trimmed Mean
        results['manhattan_robust'] = self._verify_single_method(
            'manhattan', Y_train_original, Y_score, use_robust=True, outlier_method='none'
        )
        
        # Mahalanobis + Robust Covariance (skip for small datasets)
        if n_samples < 20:
            print(f"  [Mahalanobis + Robust Stats    ] ⚠️ Skipped (dataset too small: {n_samples} samples < 20)")
            results['mahalanobis_robust'] = {
                'result': True,  # Default to accept to not bias consensus
                'score': 0.0,
                'threshold': 0.0,
                'msg': 'Skipped (dataset too small for reliable covariance)',
                'n_samples_used': n_samples,
                'outlier_method': 'none',
                'use_robust_stats': True,
                'skipped': True
            }
        else:
            results['mahalanobis_robust'] = self._verify_single_method(
                'mahalanobis', Y_train_original, Y_score, use_robust=True, outlier_method='none'
            )
        
        # ===================================================================
        # DETERMINE BEST METHOD
        # ===================================================================
        
        recommended_method = self._select_best_method(results)
        consensus = self._calculate_consensus(results)
        
        # Training data quality metrics
        training_quality = {
            'n_samples_original': int(Y_train_original.shape[0]),
            'n_samples_after_iqr': int(len(self._remove_outliers_iqr(Y_train_original.copy()))),
            'n_samples_after_zscore': int(len(self._remove_outliers_zscore(Y_train_original.copy()))),
            'n_samples_after_iforest': int(len(self._remove_outliers_iforest(Y_train_original.copy()))),
        }
        
        print("\n" + "="*60)
        print(f"⭐ RECOMMENDED: {recommended_method}")
        print(f"🎯 CONSENSUS: {consensus['accept_count']}/{consensus['total_count']} methods accept")
        print("="*60 + "\n")
        
        return {
            "error": False,
            "results": results,
            "recommended": str(recommended_method),
            "consensus": consensus,
            "training_quality": training_quality,
            "final_decision": bool(results[recommended_method]['result']),
            "final_score": float(results[recommended_method]['score']),
            "msg": str(results[recommended_method]['msg'])
        }
    
    def _verify_single_method(self, method, Y_train, Y_score, use_robust=False, outlier_method='none'):
        """Helper to verify with a single method configuration"""
        
        # Apply outlier removal if specified
        if outlier_method == 'iqr':
            Y_train_clean = self._remove_outliers_iqr(Y_train.copy())
            method_label = f"{method.capitalize()} + IQR"
        elif outlier_method == 'zscore':
            Y_train_clean = self._remove_outliers_zscore(Y_train.copy())
            method_label = f"{method.capitalize()} + Z-Score"
        elif outlier_method == 'iforest':
            Y_train_clean = self._remove_outliers_iforest(Y_train.copy())
            method_label = f"{method.capitalize()} + Isolation Forest"
        else:
            Y_train_clean = Y_train.copy()
            if use_robust:
                method_label = f"{method.capitalize()} + Robust Stats"
            else:
                method_label = method.capitalize()
        
        # Ensure we still have enough samples
        if len(Y_train_clean) < 3:
            print(f"  [{method_label}] ⚠️ Too few samples after outlier removal, using original data")
            Y_train_clean = Y_train
        
        # Calculate adaptive threshold
        self.method = method
        self.use_robust_stats = use_robust
        
        adaptive_threshold = self._calculate_adaptive_threshold(Y_train_clean, false_accept_rate=0.05)
        
        # Train and score
        try:
            if method == 'euclidean':
                model = self._train_euclidean(Y_train_clean)
                raw_score = self._score_euclidean(model, Y_score)[0]
            elif method == 'manhattan':
                model = self._train_manhattan(Y_train_clean)
                raw_score = self._score_manhattan(model, Y_score)[0]
            elif method == 'mahalanobis':
                model = self._train_mahalanobis(Y_train_clean)
                raw_score = self._score_mahalanobis(model, Y_score)[0]
            else:
                return None
        except Exception as e:
            print(f"  [{method_label}] ❌ Scoring error: {str(e)}")
            return {
                "result": False,
                "score": 1.0,
                "raw_score": 1.0,
                "threshold": adaptive_threshold,
                "method": method_label,
                "msg": f"❌ Error: {str(e)}",
                "n_samples_used": len(Y_train_clean)
            }
        
        # Normalize score
        normalized_score = float(min(raw_score / 100.0, 1.0))
        
        # Decision using adaptive threshold
        is_genuine = bool(normalized_score <= adaptive_threshold)
        
        result_msg = (
            f"✅ Accept (score: {normalized_score:.3f} ≤ {adaptive_threshold:.3f})" 
            if is_genuine else 
            f"❌ Reject (score: {normalized_score:.3f} > {adaptive_threshold:.3f})"
        )
        
        print(f"  [{method_label:30s}] {result_msg}")
        
        return {
            "result": is_genuine,
            "score": float(normalized_score),
            "raw_score": float(raw_score),
            "threshold": float(adaptive_threshold),
            "method": str(method_label),
            "msg": str(result_msg),
            "n_samples_used": int(len(Y_train_clean)),
            "outlier_method": str(outlier_method),
            "use_robust_stats": bool(use_robust)
        }
    
    def _select_best_method(self, results):
        """Select the recommended method based on results"""
        
        # Priority: Outlier-robust methods with lowest scores
        candidates = [
            'euclidean_iforest',
            'euclidean_iqr',
            'euclidean_zscore',
            'euclidean_robust',
            'manhattan_robust',
            'euclidean',
            'manhattan',
            'mahalanobis'
        ]
        
        for candidate in candidates:
            if candidate in results and results[candidate] is not None:
                return candidate
        
        return 'euclidean'  # Fallback
    
    def _calculate_consensus(self, results):
        """Calculate how many methods agree on the decision (excluding skipped methods)"""
        
        # Filter out None results and skipped methods
        valid_results = [r for r in results.values() if r is not None and not r.get('skipped', False)]
        
        if len(valid_results) == 0:
            return {"accept_count": 0, "reject_count": 0, "total_count": 0, "agreement_percentage": 0.0}
        
        accept_count = sum(1 for r in valid_results if r['result'] == True)
        reject_count = len(valid_results) - accept_count
        
        return {
            "accept_count": int(accept_count),
            "reject_count": int(reject_count),
            "total_count": int(len(valid_results)),
            "agreement_percentage": float((max(accept_count, reject_count) / len(valid_results)) * 100)
        }