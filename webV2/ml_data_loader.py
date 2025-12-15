"""
ML Data Loader for Keystroke Dynamics Dataset
==============================================

This module provides utilities to load and preprocess keystroke dynamics data
from CSV for machine learning training.

Features:
- Automatic JSON parsing for vectors and features
- Feature matrix building (31 or 62 features)
- Label encoding for usernames
- Data filtering (enrollment only, quality checks)
- Train/test splitting with stratification

Usage:
    from ml_data_loader import KeystrokeDataLoader
    
    loader = KeystrokeDataLoader('biometric_auth.csv')
    X, y = loader.load_vectors()  # Load 31 timing features
    X_train, X_test, y_train, y_test = loader.train_test_split()
"""

import pandas as pd
import numpy as np
import json
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler


class KeystrokeDataLoader:
    """
    Load and preprocess keystroke dynamics dataset for ML training.
    """
    
    def __init__(self, csv_path='biometric_auth.csv'):
        """
        Initialize data loader.
        
        Args:
            csv_path (str): Path to CSV file
        """
        self.csv_path = csv_path
        self.df = None
        self.label_encoder = LabelEncoder()
        self.scaler = StandardScaler()
        
        print(f"[INFO] Loading data from: {csv_path}")
        self._load_csv()
        self._parse_json_columns()
        
    def _load_csv(self):
        """Load CSV file into pandas DataFrame"""
        try:
            self.df = pd.read_csv(self.csv_path)
            print(f"[SUCCESS] Loaded {len(self.df)} samples")
            print(f"[INFO] Users: {self.df['username'].nunique()}")
            print(f"[INFO] Columns: {len(self.df.columns)}")
        except pd.errors.ParserError as e:
            print(f"[WARNING] CSV has formatting issues: {e}")
            print("[INFO] Attempting recovery (skipping corrupted rows)...")
            self.df = pd.read_csv(self.csv_path, on_bad_lines='skip', engine='python')
            print(f"[SUCCESS] Recovered {len(self.df)} valid samples")
        except FileNotFoundError:
            raise FileNotFoundError(f"CSV file not found: {self.csv_path}")
        except Exception as e:
            raise Exception(f"Error loading CSV: {e}")
    
    def _parse_json_columns(self):
        """Parse JSON strings in vector and feature columns"""
        print("[INFO] Parsing JSON columns...")
        
        # Vector columns (arrays)
        vector_cols = ['H_vector', 'DD_vector', 'UD_vector', 'UU_vector', 'DU_vector']
        for col in vector_cols:
            if col in self.df.columns:
                self.df[col] = self.df[col].apply(self._safe_json_loads)
        
        # Feature columns (dicts)
        feature_cols = ['H_features', 'DD_features', 'UD_features', 'UU_features', 'DU_features']
        for col in feature_cols:
            if col in self.df.columns:
                self.df[col] = self.df[col].apply(self._safe_json_loads)
        
        # Array columns
        array_cols = ['char_sequence', 'keys_sequence']
        for col in array_cols:
            if col in self.df.columns:
                self.df[col] = self.df[col].apply(self._safe_json_loads)
        
        print("[SUCCESS] JSON parsing complete")
    
    def _safe_json_loads(self, value):
        """Safely parse JSON string"""
        if pd.isna(value):
            return None
        if isinstance(value, str):
            try:
                return json.loads(value)
            except:
                return None
        return value
    
    def filter_data(self, data_type='enrollment', min_samples_per_user=5, max_backspace=3):
        """
        Filter dataset based on quality criteria.
        
        Args:
            data_type (str): 'enrollment', 'login_attempt', or 'all'
            min_samples_per_user (int): Minimum samples required per user
            max_backspace (int): Maximum backspace count allowed
            
        Returns:
            KeystrokeDataLoader: Self for method chaining
        """
        print(f"\n[INFO] Filtering data...")
        original_count = len(self.df)
        
        # Filter by data type
        if data_type != 'all':
            self.df = self.df[self.df['data_type'] == data_type]
            print(f"  - After data_type filter: {len(self.df)} samples")
        
        # Filter by backspace count
        if max_backspace is not None:
            self.df = self.df[self.df['backspace_count'] <= max_backspace]
            print(f"  - After backspace filter: {len(self.df)} samples")
        
        # Filter users with insufficient samples
        if min_samples_per_user > 0:
            user_counts = self.df['username'].value_counts()
            valid_users = user_counts[user_counts >= min_samples_per_user].index
            self.df = self.df[self.df['username'].isin(valid_users)]
            print(f"  - After min_samples filter: {len(self.df)} samples, {len(valid_users)} users")
        
        removed = original_count - len(self.df)
        print(f"[SUCCESS] Filtered: Removed {removed} samples, kept {len(self.df)}")
        
        return self
    
    def load_vectors(self, normalize=True):
        """
        Load raw timing vectors (31 features).
        
        Args:
            normalize (bool): Apply StandardScaler normalization
            
        Returns:
            tuple: (X, y) where X is feature matrix, y is labels
        """
        print("\n[INFO] Building feature matrix from vectors...")
        
        # Build feature matrix
        X = []
        y = []
        
        for idx, row in self.df.iterrows():
            try:
                features = []
                
                # Combine all 5 vectors
                features.extend(row['H_vector'] or [])
                features.extend(row['DD_vector'] or [])
                features.extend(row['UD_vector'] or [])
                features.extend(row['UU_vector'] or [])
                features.extend(row['DU_vector'] or [])
                
                # Validate
                if len(features) > 0:
                    X.append(features)
                    y.append(row['username'])
                    
            except Exception as e:
                print(f"[WARNING] Skipping row {idx}: {e}")
        
        X = np.array(X)
        y = np.array(y)
        
        print(f"[SUCCESS] Feature matrix shape: {X.shape}")
        print(f"[INFO] Feature count per sample: {X.shape[1]}")
        
        # Normalize
        if normalize:
            X = self.scaler.fit_transform(X)
            print("[INFO] Features normalized (StandardScaler)")
        
        # Encode labels
        y_encoded = self.label_encoder.fit_transform(y)
        print(f"[INFO] Labels encoded: {len(self.label_encoder.classes_)} classes")
        print(f"[INFO] Classes: {list(self.label_encoder.classes_)}")
        
        return X, y_encoded
    
    def load_labeled_features(self, normalize=True):
        """
        Load labeled features (62 features - more interpretable).
        
        Args:
            normalize (bool): Apply StandardScaler normalization
            
        Returns:
            tuple: (X, y) where X is feature matrix, y is labels
        """
        print("\n[INFO] Building feature matrix from labeled features...")
        
        X = []
        y = []
        
        for idx, row in self.df.iterrows():
            try:
                features = []
                
                # Extract values from each feature dict
                for col in ['H_features', 'DD_features', 'UD_features', 'UU_features', 'DU_features']:
                    if row[col] and isinstance(row[col], dict):
                        # Sort keys for consistent ordering
                        sorted_keys = sorted(row[col].keys())
                        features.extend([row[col][k] for k in sorted_keys])
                
                if len(features) > 0:
                    X.append(features)
                    y.append(row['username'])
                    
            except Exception as e:
                print(f"[WARNING] Skipping row {idx}: {e}")
        
        X = np.array(X)
        y = np.array(y)
        
        print(f"[SUCCESS] Feature matrix shape: {X.shape}")
        print(f"[INFO] Feature count per sample: {X.shape[1]}")
        
        # Normalize
        if normalize:
            X = self.scaler.fit_transform(X)
            print("[INFO] Features normalized")
        
        # Encode labels
        y_encoded = self.label_encoder.fit_transform(y)
        print(f"[INFO] Labels encoded: {len(self.label_encoder.classes_)} classes")
        
        return X, y_encoded
    
    def load_combined_features(self, include_global=True, normalize=True):
        """
        Load vectors + global metrics (33 features).
        
        Args:
            include_global (bool): Include total_duration and typing_rollover_ratio
            normalize (bool): Apply StandardScaler normalization
            
        Returns:
            tuple: (X, y)
        """
        print("\n[INFO] Building combined feature matrix...")
        
        X = []
        y = []
        
        for idx, row in self.df.iterrows():
            try:
                features = []
                
                # Add timing vectors
                features.extend(row['H_vector'] or [])
                features.extend(row['DD_vector'] or [])
                features.extend(row['UD_vector'] or [])
                features.extend(row['UU_vector'] or [])
                features.extend(row['DU_vector'] or [])
                
                # Add global metrics
                if include_global:
                    features.append(row['total_duration'])
                    features.append(row['typing_rollover_ratio'])
                
                if len(features) > 0:
                    X.append(features)
                    y.append(row['username'])
                    
            except Exception as e:
                print(f"[WARNING] Skipping row {idx}: {e}")
        
        X = np.array(X)
        y = np.array(y)
        
        print(f"[SUCCESS] Feature matrix shape: {X.shape}")
        
        if normalize:
            X = self.scaler.fit_transform(X)
            print("[INFO] Features normalized")
        
        y_encoded = self.label_encoder.fit_transform(y)
        print(f"[INFO] Labels encoded: {len(self.label_encoder.classes_)} classes")
        
        return X, y_encoded
    
    def train_test_split(self, X, y, test_size=0.2, random_state=42):
        """
        Split data into train and test sets with stratification.
        
        Args:
            X: Feature matrix
            y: Labels (encoded)
            test_size (float): Proportion of test set (0.2 = 20%)
            random_state (int): Random seed for reproducibility
            
        Returns:
            tuple: (X_train, X_test, y_train, y_test)
        """
        print(f"\n[INFO] Splitting data: {int((1-test_size)*100)}% train, {int(test_size*100)}% test")
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, 
            test_size=test_size, 
            random_state=random_state,
            stratify=y  # Ensure balanced split per user
        )
        
        print(f"[SUCCESS] Train: {len(X_train)} samples, Test: {len(X_test)} samples")
        
        return X_train, X_test, y_train, y_test
    
    def get_statistics(self):
        """Print dataset statistics"""
        print("\n" + "="*60)
        print("DATASET STATISTICS")
        print("="*60)
        
        print(f"Total samples: {len(self.df)}")
        print(f"Total users: {self.df['username'].nunique()}")
        print(f"\nSamples per user:")
        print(self.df['username'].value_counts().to_string())
        
        print(f"\nData types:")
        print(self.df['data_type'].value_counts().to_string())
        
        print(f"\nBackspace distribution:")
        print(self.df['backspace_count'].value_counts().sort_index().to_string())
        
        print(f"\nDuration statistics:")
        print(f"  Mean: {self.df['total_duration'].mean():.2f}s")
        print(f"  Std:  {self.df['total_duration'].std():.2f}s")
        print(f"  Min:  {self.df['total_duration'].min():.2f}s")
        print(f"  Max:  {self.df['total_duration'].max():.2f}s")
        
        print("="*60)


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

if __name__ == "__main__":
    print("="*60)
    print("KEYSTROKE DYNAMICS ML DATA LOADER - DEMO")
    print("="*60)
    
    # Example 1: Basic usage
    print("\n--- EXAMPLE 1: Basic Vector Loading ---")
    loader = KeystrokeDataLoader('biometric_auth.csv')
    loader.get_statistics()
    
    # Filter high-quality samples
    loader.filter_data(
        data_type='enrollment',
        min_samples_per_user=2,
        max_backspace=0  # Only perfect typing
    )
    
    # Load vectors
    X, y = loader.load_vectors(normalize=True)
    print(f"\nReady for ML training:")
    print(f"  X shape: {X.shape}")
    print(f"  y shape: {y.shape}")
    print(f"  Classes: {loader.label_encoder.classes_}")
    
    # Split data
    X_train, X_test, y_train, y_test = loader.train_test_split(X, y, test_size=0.2)
    
    print("\n--- EXAMPLE 2: Train a Simple Model ---")
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, classification_report
    
    # Train
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    # Predict
    y_pred = model.predict(X_test)
    
    # Evaluate
    accuracy = accuracy_score(y_test, y_pred)
    print(f"\nAccuracy: {accuracy*100:.2f}%")
    print("\nClassification Report:")
    print(classification_report(
        y_test, 
        y_pred, 
        target_names=loader.label_encoder.classes_
    ))
    
    print("\n" + "="*60)
    print("✅ Data loader ready for production ML training!")
    print("="*60)
