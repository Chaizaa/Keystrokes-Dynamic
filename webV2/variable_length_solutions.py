"""
SOLUSI untuk Variable-Length Vectors dalam Keystroke Dynamics
================================================================

Problem: User pakai password berbeda-beda panjangnya
         → Vector lengths berbeda (10, 11, 13, 14, 15, 16)

Solusi: Gunakan algoritma yang bisa handle variable-length input
"""

import numpy as np
from scipy.spatial.distance import euclidean
from scipy.stats import skew, kurtosis
import json

# ============================================================================
# SOLUTION 1: Statistical Feature Extraction (RECOMMENDED untuk ML)
# ============================================================================
# Ide: Convert variable-length vectors → fixed-size statistical features

def extract_statistical_features(vectors_dict):
    """
    Extract fixed-size features dari variable-length timing vectors
    
    Input: 
        vectors_dict = {
            'H_vector': [100, 150, 120, ...],  # length bisa beda-beda
            'DD_vector': [50, 80, 60, ...],
            'UD_vector': [...],
            'UU_vector': [...],
            'DU_vector': [...]
        }
    
    Output:
        feature_vector = [f1, f2, f3, ..., f35]  # FIXED SIZE: 35 features
    """
    features = []
    
    # Process each timing vector
    for vector_name in ['H_vector', 'DD_vector', 'UD_vector', 'UU_vector', 'DU_vector']:
        vec = vectors_dict.get(vector_name, [])
        
        if len(vec) == 0:
            # Empty vector: add zeros
            features.extend([0] * 7)
            continue
        
        vec = np.array(vec)
        
        # Statistical features (7 per vector × 5 vectors = 35 total)
        features.append(np.mean(vec))       # 1. Mean (rata-rata)
        features.append(np.std(vec))        # 2. Std deviation (variasi)
        features.append(np.min(vec))        # 3. Minimum
        features.append(np.max(vec))        # 4. Maximum
        features.append(np.median(vec))     # 5. Median
        features.append(skew(vec))          # 6. Skewness (asimetri)
        features.append(kurtosis(vec))      # 7. Kurtosis (tail distribution)
    
    return np.array(features)  # Fixed size: 35 features

# Contoh penggunaan:
sample_data = {
    'H_vector': [120, 150, 100, 180, 90, 110, 140],  # 7 elements
    'DD_vector': [50, 80, 60, 90, 40, 55, 70],       # 7 elements
    'UD_vector': [30, 40, 35, 45, 28, 32, 38],
    'UU_vector': [200, 250, 220, 280, 190, 210, 240],
    'DU_vector': [80, 100, 90, 110, 75, 85, 95]
}

features1 = extract_statistical_features(sample_data)
print("SOLUTION 1: Statistical Features")
print("=" * 70)
print(f"Input: Variable length vectors (length={len(sample_data['H_vector'])})")
print(f"Output: Fixed-size feature vector (shape={features1.shape})")
print(f"Features: {features1[:10]}... (showing first 10)")
print(f"\n✅ Keuntungan:")
print("   - Fixed size output → bisa langsung dipakai untuk ML")
print("   - Fast computation")
print("   - Works dengan ANY password length")
print("   - Feature interpretable (statistik)")


# ============================================================================
# SOLUTION 2: Dynamic Time Warping (DTW) Distance
# ============================================================================
# Ide: Compare sequences dengan panjang berbeda menggunakan DTW

def dtw_distance(seq1, seq2):
    """
    Dynamic Time Warping distance untuk compare 2 sequences dengan length berbeda
    
    Contoh:
        seq1 = [100, 150, 120]        # length 3
        seq2 = [100, 140, 130, 125]   # length 4
        
    DTW akan find optimal alignment:
        seq1: 100 --- 150 --- 120 ---
        seq2: 100 140 130 --- 125 ---
              |    |    |        |
             match warp warp   warp
    """
    n, m = len(seq1), len(seq2)
    
    # Initialize DTW matrix
    dtw_matrix = np.zeros((n + 1, m + 1))
    for i in range(n + 1):
        for j in range(m + 1):
            dtw_matrix[i, j] = np.inf
    dtw_matrix[0, 0] = 0
    
    # Fill DTW matrix
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = abs(seq1[i-1] - seq2[j-1])
            dtw_matrix[i, j] = cost + min(
                dtw_matrix[i-1, j],      # insertion
                dtw_matrix[i, j-1],      # deletion
                dtw_matrix[i-1, j-1]     # match
            )
    
    return dtw_matrix[n, m]

def verify_with_dtw(enrollment_vectors, login_vectors, threshold=1000):
    """
    Verify user menggunakan DTW untuk compare variable-length vectors
    """
    # Compute DTW distance untuk setiap vector type
    distances = []
    
    for vector_name in ['H_vector', 'DD_vector', 'UD_vector']:
        enroll_vec = enrollment_vectors.get(vector_name, [])
        login_vec = login_vectors.get(vector_name, [])
        
        if len(enroll_vec) > 0 and len(login_vec) > 0:
            dist = dtw_distance(enroll_vec, login_vec)
            distances.append(dist)
    
    # Average DTW distance
    avg_distance = np.mean(distances) if distances else float('inf')
    
    # Decision
    is_genuine = avg_distance < threshold
    
    return {
        'is_genuine': is_genuine,
        'distance': avg_distance,
        'threshold': threshold
    }

# Contoh penggunaan:
enrollment = {
    'H_vector': [120, 150, 100, 180, 90, 110, 140],  # 7 elements
    'DD_vector': [50, 80, 60, 90, 40, 55, 70],
    'UD_vector': [30, 40, 35, 45, 28, 32, 38]
}

login_attempt = {
    'H_vector': [125, 155, 95, 175, 95],  # 5 elements (DIFFERENT LENGTH!)
    'DD_vector': [48, 85, 58, 92, 38],
    'UD_vector': [32, 38, 37, 43, 30]
}

result = verify_with_dtw(enrollment, login_attempt, threshold=500)
print("\n\nSOLUTION 2: Dynamic Time Warping (DTW)")
print("=" * 70)
print(f"Enrollment vector length: {len(enrollment['H_vector'])}")
print(f"Login vector length:      {len(login_attempt['H_vector'])}")
print(f"DTW Distance:             {result['distance']:.2f}")
print(f"Decision:                 {'✅ GENUINE' if result['is_genuine'] else '❌ IMPOSTOR'}")
print(f"\n✅ Keuntungan:")
print("   - Bisa compare sequences dengan panjang BERBEDA")
print("   - Robust terhadap timing variations")
print("   - Good for verification/authentication")


# ============================================================================
# SOLUTION 3: Recurrent Neural Networks (LSTM/GRU)
# ============================================================================
# Ide: LSTM/GRU bisa handle variable-length sequences

def prepare_for_lstm(vectors_dict, max_length=None):
    """
    Prepare data untuk LSTM/GRU input dengan padding
    
    Tapi BERBEDA dengan simple padding:
    - LSTM bisa di-train dengan "masking" layer
    - Model akan ignore padded values (0s)
    """
    # Concatenate all vectors
    all_vectors = []
    for vector_name in ['H_vector', 'DD_vector', 'UD_vector', 'UU_vector', 'DU_vector']:
        vec = vectors_dict.get(vector_name, [])
        all_vectors.extend(vec)
    
    # Determine max_length if not specified
    if max_length is None:
        max_length = len(all_vectors)
    
    # Pad to max_length
    if len(all_vectors) < max_length:
        all_vectors.extend([0] * (max_length - len(all_vectors)))
    else:
        all_vectors = all_vectors[:max_length]
    
    return np.array(all_vectors).reshape(1, -1, 1)  # Shape: (batch, timesteps, features)

print("\n\nSOLUTION 3: LSTM/GRU Networks (Keras)")
print("=" * 70)
print("```python")
print("from tensorflow.keras.models import Sequential")
print("from tensorflow.keras.layers import LSTM, Dense, Masking")
print("")
print("# Build model with Masking layer")
print("model = Sequential([")
print("    Masking(mask_value=0., input_shape=(None, 1)),  # Ignore padded 0s")
print("    LSTM(64, return_sequences=True),")
print("    LSTM(32),")
print("    Dense(1, activation='sigmoid')  # Binary: genuine vs impostor")
print("])")
print("")
print("# Train with variable-length sequences")
print("model.compile(optimizer='adam', loss='binary_crossentropy')")
print("```")
print(f"\n✅ Keuntungan:")
print("   - Model bisa LEARN patterns dari variable-length data")
print("   - Masking layer akan ignore padded values")
print("   - State-of-the-art untuk sequential data")
print("   - No manual feature engineering needed")


# ============================================================================
# SOLUTION 4: Siamese Networks (Recommended untuk Authentication)
# ============================================================================
print("\n\nSOLUTION 4: Siamese Networks (Best for Keystroke Auth)")
print("=" * 70)
print("Architecture: Compare 2 samples using shared LSTM encoder")
print("")
print("```python")
print("from tensorflow.keras.layers import Input, LSTM, Lambda")
print("from tensorflow.keras.models import Model")
print("import tensorflow.keras.backend as K")
print("")
print("# Shared LSTM encoder")
print("def create_encoder():")
print("    return Sequential([")
print("        Masking(mask_value=0.),")
print("        LSTM(64),")
print("        Dense(32, activation='relu')")
print("    ])")
print("")
print("# Siamese architecture")
print("input_a = Input(shape=(None, 1))  # Variable length!")
print("input_b = Input(shape=(None, 1))")
print("")
print("encoder = create_encoder()")
print("encoded_a = encoder(input_a)")
print("encoded_b = encoder(input_b)")
print("")
print("# Compute distance between encodings")
print("distance = Lambda(lambda x: K.abs(x[0] - x[1]))([encoded_a, encoded_b])")
print("output = Dense(1, activation='sigmoid')(distance)")
print("")
print("siamese = Model(inputs=[input_a, input_b], outputs=output)")
print("```")
print(f"\n✅ Keuntungan:")
print("   - BEST untuk authentication (compare enrollment vs login)")
print("   - Handle variable length automatically")
print("   - Learn similarity metric directly")
print("   - Used in production systems (FaceID, etc.)")


# ============================================================================
# COMPARISON & RECOMMENDATION
# ============================================================================
print("\n\n" + "=" * 70)
print("📊 PERBANDINGAN SOLUSI")
print("=" * 70)
print(f"{'Method':<25} | {'Variable Len':<12} | {'Speed':<8} | {'Accuracy':<10} | {'Complexity':<10}")
print("-" * 70)
print(f"{'1. Statistical Features':<25} | {'✅ Yes':<12} | {'⚡ Fast':<8} | {'⭐⭐⭐':<10} | {'🟢 Easy':<10}")
print(f"{'2. DTW Distance':<25} | {'✅ Yes':<12} | {'🐌 Slow':<8} | {'⭐⭐⭐⭐':<10} | {'🟡 Medium':<10}")
print(f"{'3. LSTM/GRU':<25} | {'✅ Yes':<12} | {'⚡ Fast':<8} | {'⭐⭐⭐⭐':<10} | {'🔴 Hard':<10}")
print(f"{'4. Siamese Networks':<25} | {'✅ Yes':<12} | {'⚡ Fast':<8} | {'⭐⭐⭐⭐⭐':<10} | {'🔴 Hard':<10}")

print("\n\n🎯 REKOMENDASI untuk Thesis:")
print("=" * 70)
print("\n1. 🥇 START dengan: Statistical Features (Solution 1)")
print("   Alasan:")
print("   - Paling mudah diimplementasi")
print("   - Fast training & inference")
print("   - Bisa pakai algoritma ML klasik (SVM, Random Forest)")
print("   - Good baseline untuk thesis")
print("")
print("2. 🥈 UPGRADE ke: DTW Distance (Solution 2)")
print("   Alasan:")
print("   - Proven method dalam keystroke dynamics literature")
print("   - No training needed (distance-based)")
print("   - Bisa jadi comparison di thesis (Feature-based vs DTW-based)")
print("")
print("3. 🥉 ADVANCED (optional): Siamese Networks (Solution 4)")
print("   Alasan:")
print("   - State-of-the-art approach")
print("   - Good untuk 'future work' section di thesis")
print("   - Butuh GPU & lebih banyak data")

print("\n\n💡 Implementation Plan:")
print("=" * 70)
print("Phase 1: Implement Statistical Features")
print("   → Update verifier.py untuk extract features")
print("   → Train SVM/Random Forest classifier")
print("   → Evaluate: EER, FAR, FRR")
print("")
print("Phase 2: Add DTW as comparison")
print("   → Implement DTW verification")
print("   → Compare performance: Features vs DTW")
print("   → Write thesis comparison section")
print("")
print("Phase 3 (optional): Deep Learning")
print("   → Implement Siamese Network")
print("   → Show improvement over classical methods")
print("   → Good untuk publikasi jurnal!")
