"""
Dataset Validation Script
=========================

Validate keystroke dynamics dataset before ML training.

Checks:
- CSV file integrity
- JSON parsing errors
- Missing values
- Feature vector lengths
- User sample distribution
- Data quality metrics

Usage:
    python validate_dataset.py
"""

import pandas as pd
import json
import numpy as np
from collections import Counter


class DatasetValidator:
    """Validate keystroke dynamics dataset"""
    
    def __init__(self, csv_path='biometric_auth.csv'):
        self.csv_path = csv_path
        self.df = None
        self.errors = []
        self.warnings = []
        
    def run_all_checks(self):
        """Run all validation checks"""
        print("="*70)
        print("KEYSTROKE DYNAMICS DATASET VALIDATION")
        print("="*70)
        
        checks = [
            ("Loading CSV", self.check_csv_load),
            ("Column Integrity", self.check_columns),
            ("JSON Parsing", self.check_json_parsing),
            ("Missing Values", self.check_missing_values),
            ("Vector Lengths", self.check_vector_lengths),
            ("User Distribution", self.check_user_distribution),
            ("Data Quality", self.check_data_quality),
            ("Feature Consistency", self.check_feature_consistency),
        ]
        
        for check_name, check_func in checks:
            print(f"\n[CHECK] {check_name}...")
            try:
                check_func()
                print(f"  ✅ PASS")
            except Exception as e:
                print(f"  ❌ FAIL: {e}")
                self.errors.append(f"{check_name}: {e}")
        
        self.print_summary()
        
    def check_csv_load(self):
        """Check if CSV can be loaded"""
        self.df = pd.read_csv(self.csv_path, on_bad_lines='warn', engine='python')
        if len(self.df) == 0:
            raise ValueError("CSV is empty")
        print(f"  - Loaded {len(self.df)} samples")
        
    def check_columns(self):
        """Check if all required columns exist"""
        required_cols = [
            'username', 'timestamp', 'password_hash',
            'H_vector', 'DD_vector', 'UD_vector', 'UU_vector', 'DU_vector',
            'H_features', 'DD_features', 'UD_features', 'UU_features', 'DU_features',
            'total_duration', 'backspace_count', 'typing_rollover_ratio',
            'data_type'
        ]
        
        missing = [col for col in required_cols if col not in self.df.columns]
        if missing:
            raise ValueError(f"Missing columns: {missing}")
        
        print(f"  - All {len(required_cols)} required columns present")
        
    def check_json_parsing(self):
        """Check if JSON strings can be parsed"""
        json_cols = [
            'H_vector', 'DD_vector', 'UD_vector', 'UU_vector', 'DU_vector',
            'H_features', 'DD_features', 'UD_features', 'UU_features', 'DU_features',
            'char_sequence', 'keys_sequence'
        ]
        
        errors = []
        for col in json_cols:
            if col not in self.df.columns:
                continue
                
            for idx, value in enumerate(self.df[col]):
                if pd.isna(value):
                    continue
                try:
                    json.loads(value)
                except:
                    errors.append(f"Row {idx}, Column {col}")
        
        if errors:
            raise ValueError(f"JSON parsing errors in: {errors[:5]}")
        
        print(f"  - All JSON columns parseable")
        
    def check_missing_values(self):
        """Check for missing critical values"""
        critical_cols = ['username', 'H_vector', 'DD_vector', 'UD_vector']
        
        for col in critical_cols:
            missing_count = self.df[col].isna().sum()
            if missing_count > 0:
                self.warnings.append(f"{col}: {missing_count} missing values")
        
        if self.warnings:
            print(f"  ⚠️  Found {len(self.warnings)} warnings")
        else:
            print(f"  - No missing critical values")
        
    def check_vector_lengths(self):
        """Check if vector lengths are consistent per user"""
        # Parse vectors
        vector_cols = ['H_vector', 'DD_vector', 'UD_vector', 'UU_vector', 'DU_vector']
        
        for col in vector_cols:
            lengths = []
            for value in self.df[col]:
                try:
                    vec = json.loads(value)
                    lengths.append(len(vec))
                except:
                    pass
            
            if lengths:
                length_counts = Counter(lengths)
                dominant_length = length_counts.most_common(1)[0][0]
                inconsistent = sum(1 for l in lengths if l != dominant_length)
                
                if inconsistent > 0:
                    self.warnings.append(
                        f"{col}: {inconsistent}/{len(lengths)} samples have inconsistent length"
                    )
        
        print(f"  - Vector length checks complete")
        
    def check_user_distribution(self):
        """Check user sample distribution"""
        user_counts = self.df['username'].value_counts()
        
        print(f"  - Users: {len(user_counts)}")
        print(f"  - Samples per user:")
        for user, count in user_counts.items():
            status = "✅" if count >= 10 else "⚠️" if count >= 5 else "❌"
            print(f"    {status} {user}: {count} samples")
        
        # Check if any user has < 5 samples
        insufficient = user_counts[user_counts < 5]
        if len(insufficient) > 0:
            self.warnings.append(
                f"{len(insufficient)} users have < 5 samples (not enough for ML)"
            )
        
    def check_data_quality(self):
        """Check data quality metrics"""
        # Backspace count
        high_backspace = self.df[self.df['backspace_count'] > 3]
        if len(high_backspace) > 0:
            self.warnings.append(
                f"{len(high_backspace)} samples have >3 backspaces (noisy)"
            )
        
        # Duration outliers
        mean_dur = self.df['total_duration'].mean()
        std_dur = self.df['total_duration'].std()
        outliers = self.df[
            (self.df['total_duration'] < mean_dur - 3*std_dur) |
            (self.df['total_duration'] > mean_dur + 3*std_dur)
        ]
        if len(outliers) > 0:
            self.warnings.append(
                f"{len(outliers)} samples are duration outliers (>3 std)"
            )
        
        print(f"  - Quality metrics checked")
        
    def check_feature_consistency(self):
        """Check if labeled features match vector lengths"""
        for idx, row in self.df.iterrows():
            try:
                # Check H_vector vs H_features
                h_vec = json.loads(row['H_vector'])
                h_feat = json.loads(row['H_features'])
                
                if len(h_vec) != len(h_feat):
                    self.warnings.append(
                        f"Row {idx}: H_vector length ({len(h_vec)}) != H_features count ({len(h_feat)})"
                    )
                    
            except:
                pass
        
        print(f"  - Feature consistency checked")
        
    def print_summary(self):
        """Print validation summary"""
        print("\n" + "="*70)
        print("VALIDATION SUMMARY")
        print("="*70)
        
        if len(self.errors) == 0 and len(self.warnings) == 0:
            print("✅ All checks passed! Dataset is ready for ML training.")
        else:
            if self.errors:
                print(f"\n❌ ERRORS ({len(self.errors)}):")
                for error in self.errors:
                    print(f"  - {error}")
            
            if self.warnings:
                print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
                for warning in self.warnings:
                    print(f"  - {warning}")
        
        print("\nRECOMMENDATIONS:")
        
        if len(self.errors) > 0:
            print("  ❌ Fix errors before training")
        elif len(self.warnings) > 5:
            print("  ⚠️  Address warnings to improve data quality")
        else:
            print("  ✅ Dataset quality is acceptable")
            print("  ✅ Proceed with data collection or ML training")
        
        print("="*70)


if __name__ == "__main__":
    validator = DatasetValidator('biometric_auth.csv')
    validator.run_all_checks()
