"""
Quick test of ML pipeline after collecting samples
Run this after you have at least 2-3 samples in CSV
"""

import os
from ml_data_loader import KeystrokeDataLoader

csv_path = 'biometric_auth.csv'

if not os.path.exists(csv_path):
    print("❌ CSV file not found. Collect samples first!")
    exit()

print("="*70)
print("TESTING ML PIPELINE")
print("="*70)

# Load data
loader = KeystrokeDataLoader(csv_path)
print(f"\n✅ CSV loaded: {len(loader.df)} samples")

# Try vectors
try:
    X, y = loader.load_vectors(normalize=False)
    print(f"✅ Vector loading works: {X.shape}")
except Exception as e:
    print(f"❌ Vector loading failed: {e}")

# Try labeled features
try:
    loader = KeystrokeDataLoader(csv_path)  # Reload
    X, y = loader.load_labeled_features(normalize=False)
    print(f"✅ Labeled features work: {X.shape}")
except Exception as e:
    print(f"❌ Labeled features failed: {e}")

# Try combined
try:
    loader = KeystrokeDataLoader(csv_path)  # Reload
    X, y = loader.load_combined_features(normalize=False)
    print(f"✅ Combined features work: {X.shape}")
except Exception as e:
    print(f"❌ Combined features failed: {e}")

print("\n" + "="*70)
print("PIPELINE TEST COMPLETE")
print("="*70)

# If all passed, show sample training example
if len(loader.df) >= 4:
    print("\n💡 You have enough samples to test training!")
    print("   Try running a quick Random Forest test:")
    print("   python -c \"from ml_data_loader import KeystrokeDataLoader; from sklearn.ensemble import RandomForestClassifier; loader = KeystrokeDataLoader('biometric_auth.csv'); X, y = loader.load_vectors(normalize=True); print('Training...'); model = RandomForestClassifier(n_estimators=50, random_state=42); model.fit(X, y); print(f'✅ Model trained on {len(X)} samples'); print(f'Training accuracy: {model.score(X, y):.2%}')\"")
else:
    print(f"\n📊 Current samples: {len(loader.df)}")
    print("   Collect at least 4-6 samples (2 users × 2-3 each) for training test")
