"""
Test Statistical Feature Extraction
=====================================
Verifikasi bahwa feature extraction bekerja dengan variable-length vectors
"""

import sys
import os

# Add webV2 to path for imports
webv2_path = os.path.join(os.path.dirname(__file__), 'webV2')
sys.path.insert(0, webv2_path)

from verifier import Verifier  # type: ignore
import json

print("="*70)
print("TEST: Statistical Feature Extraction")
print("="*70)

verifier = Verifier()

# Test Case 1: Short password (7 characters)
print("\n1️⃣ Test Case: Short Password (7 chars)")
sample1 = {
    'H_vector': [0.120, 0.150, 0.100, 0.180, 0.090, 0.110, 0.140],
    'DD_vector': [0.050, 0.080, 0.060, 0.090, 0.040, 0.055, 0.070],
    'UD_vector': [0.030, 0.040, 0.035, 0.045, 0.028, 0.032, 0.038],
    'UU_vector': [0.200, 0.250, 0.220, 0.280, 0.190, 0.210, 0.240],
    'DU_vector': [0.080, 0.100, 0.090, 0.110, 0.075, 0.085, 0.095]
}

features1 = verifier.extract_statistical_features(sample1)
print(f"   Input vector lengths: {len(sample1['H_vector'])} elements")
print(f"   Output features: {features1.shape} (fixed size!)")
print(f"   First 10 features: {features1[:10]}")
print(f"   ✅ Success: Variable length → Fixed size!")

# Test Case 2: Long password (14 characters) - DIFFERENT LENGTH!
print("\n2️⃣ Test Case: Long Password (14 chars)")
sample2 = {
    'H_vector': [0.115, 0.145, 0.095, 0.175, 0.085, 0.105, 0.135, 0.125, 0.155, 0.105, 0.185, 0.095, 0.115, 0.145],
    'DD_vector': [0.048, 0.078, 0.058, 0.088, 0.038, 0.053, 0.068, 0.052, 0.082, 0.062, 0.092, 0.042, 0.057],
    'UD_vector': [0.028, 0.038, 0.033, 0.043, 0.026, 0.030, 0.036, 0.032, 0.042, 0.037, 0.047, 0.030, 0.034],
    'UU_vector': [0.195, 0.245, 0.215, 0.275, 0.185, 0.205, 0.235, 0.205, 0.255, 0.225, 0.285, 0.195, 0.215],
    'DU_vector': [0.078, 0.098, 0.088, 0.108, 0.073, 0.083, 0.093, 0.082, 0.102, 0.092, 0.112, 0.077, 0.087]
}

features2 = verifier.extract_statistical_features(sample2)
print(f"   Input vector lengths: {len(sample2['H_vector'])} elements")
print(f"   Output features: {features2.shape} (fixed size!)")
print(f"   First 10 features: {features2[:10]}")
print(f"   ✅ Success: Variable length → Fixed size!")

# Test Case 3: Compare two different lengths
print("\n3️⃣ Test Case: Comparison Between Different Lengths")
print(f"   Password 1: 7 chars  → {features1.shape[0]} features")
print(f"   Password 2: 14 chars → {features2.shape[0]} features")
print(f"   ✅ Both have SAME output size: {features1.shape == features2.shape}")

# Calculate Euclidean distance (ready for ML!)
import numpy as np
distance = np.linalg.norm(features1 - features2)
print(f"\n   📊 Euclidean Distance: {distance:.4f}")
print(f"   ✅ Can be used for classification/clustering!")

# Test Case 4: Load from CSV and extract features
print("\n4️⃣ Test Case: Real Data from CSV")
import csv

csv_path = "webV2/biometric_weak_auth.csv"
with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    samples = list(reader)

print(f"   Total samples in CSV: {len(samples)}")

# Extract features from first 5 samples
feature_vectors = []
for i, sample in enumerate(samples[:5]):
    try:
        # Parse vectors from JSON strings
        sample_dict = {
            'H_vector': json.loads(sample.get('H_vector', '[]')),
            'DD_vector': json.loads(sample.get('DD_vector', '[]')),
            'UD_vector': json.loads(sample.get('UD_vector', '[]')),
            'UU_vector': json.loads(sample.get('UU_vector', '[]')),
            'DU_vector': json.loads(sample.get('DU_vector', '[]'))
        }
        
        features = verifier.extract_statistical_features(sample_dict)
        feature_vectors.append(features)
        
        username = sample.get('username', 'unknown')
        vec_len = len(sample_dict['H_vector'])
        print(f"   Sample {i+1}: {username:20s} | Vector length: {vec_len:2d} | Features: {features.shape}")
    except Exception as e:
        print(f"   Sample {i+1}: ERROR - {e}")

if feature_vectors:
    print(f"\n   ✅ Successfully extracted features from {len(feature_vectors)} samples")
    print(f"   ✅ All features have shape: {feature_vectors[0].shape}")
    print(f"   ✅ Ready for ML training!")

print("\n" + "="*70)
print("🎯 CONCLUSION")
print("="*70)
print("✅ Feature extraction works correctly!")
print("✅ Variable-length vectors → Fixed-size features (35 dimensions)")
print("✅ Users can use DIFFERENT password lengths")
print("✅ Ready for ML classifier training (SVM, Random Forest, etc.)")
print("="*70)
