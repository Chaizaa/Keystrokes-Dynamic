"""
Test script for comprehensive verification system
Run this to verify all components are working correctly
"""

import sys
import os

# Add webV2 to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'webV2'))

def test_verifier_imports():
    """Test if all required imports work"""
    print("\n" + "="*60)
    print("TEST 1: Checking Imports")
    print("="*60)
    
    try:
        import numpy as np
        print("✅ numpy imported successfully")
    except ImportError as e:
        print(f"❌ numpy import failed: {e}")
        return False
    
    try:
        from scipy.stats import skew, kurtosis, trim_mean
        print("✅ scipy.stats imported successfully")
    except ImportError as e:
        print(f"❌ scipy.stats import failed: {e}")
        return False
    
    try:
        from sklearn.ensemble import IsolationForest
        from sklearn.covariance import MinCovDet
        print("✅ scikit-learn imported successfully")
    except ImportError as e:
        print(f"❌ scikit-learn import failed: {e}")
        print("⚠️  Run: pip install scikit-learn")
        return False
    
    try:
        from verifier import Verifier
        print("✅ Verifier class imported successfully")
    except ImportError as e:
        print(f"❌ Verifier import failed: {e}")
        return False
    
    return True

def test_verifier_initialization():
    """Test verifier initialization with new parameters"""
    print("\n" + "="*60)
    print("TEST 2: Verifier Initialization")
    print("="*60)
    
    try:
        from verifier import Verifier
        
        # Test basic initialization
        v1 = Verifier()
        print("✅ Basic initialization: OK")
        
        # Test with outlier method
        v2 = Verifier(outlier_method='iqr')
        print("✅ IQR outlier method: OK")
        
        # Test with robust stats
        v3 = Verifier(use_robust_stats=True)
        print("✅ Robust statistics: OK")
        
        # Test with adaptive threshold
        v4 = Verifier(adaptive_threshold=True)
        print("✅ Adaptive threshold: OK")
        
        return True
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        return False

def test_outlier_methods():
    """Test outlier detection methods"""
    print("\n" + "="*60)
    print("TEST 3: Outlier Detection Methods")
    print("="*60)
    
    try:
        from verifier import Verifier
        import numpy as np
        
        verifier = Verifier()
        
        # Create sample data with outliers
        normal_data = np.random.normal(100, 10, (8, 10))  # 8 normal samples
        outlier_data = np.array([[500, 500, 500, 500, 500, 500, 500, 500, 500, 500]])  # 1 extreme outlier
        test_data = np.vstack([normal_data, outlier_data])
        
        print(f"Test data shape: {test_data.shape} (9 samples, 10 features)")
        
        # Test IQR
        clean_iqr = verifier._remove_outliers_iqr(test_data)
        print(f"✅ IQR: {len(test_data)} → {len(clean_iqr)} samples")
        
        # Test Z-Score
        clean_zscore = verifier._remove_outliers_zscore(test_data)
        print(f"✅ Z-Score: {len(test_data)} → {len(clean_zscore)} samples")
        
        # Test Isolation Forest
        clean_iforest = verifier._remove_outliers_iforest(test_data)
        print(f"✅ Isolation Forest: {len(test_data)} → {len(clean_iforest)} samples")
        
        return True
    except Exception as e:
        print(f"❌ Outlier detection failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_comprehensive_verification():
    """Test comprehensive verification with mock data"""
    print("\n" + "="*60)
    print("TEST 4: Comprehensive Verification")
    print("="*60)
    
    try:
        from verifier import Verifier
        import numpy as np
        
        verifier = Verifier()
        
        # Create mock enrollment data (10 samples)
        enrollment_samples = []
        for i in range(10):
            sample = {
                'H_vector': list(np.random.normal(100, 20, 7)),  # 7 hold times
                'DD_vector': list(np.random.normal(150, 30, 6)),  # 6 flight times
                'password_hash': 'mock_hash_12345'
            }
            enrollment_samples.append(sample)
        
        print(f"Mock enrollment: {len(enrollment_samples)} samples created")
        
        # Create mock test sample (similar to enrollment)
        test_sample = {
            'H_vector': list(np.random.normal(100, 20, 7)),
            'DD_vector': list(np.random.normal(150, 30, 6)),
            'password_hash': 'mock_hash_12345'
        }
        
        # Run comprehensive verification
        result = verifier.verify_user_comprehensive(test_sample, enrollment_samples)
        
        if result.get('error'):
            print(f"❌ Verification error: {result['msg']}")
            return False
        
        print(f"\n✅ Comprehensive verification completed!")
        print(f"   Final decision: {'ACCEPT' if result['final_decision'] else 'REJECT'}")
        print(f"   Final score: {result['final_score']:.4f}")
        print(f"   Recommended method: {result['recommended']}")
        print(f"   Consensus: {result['consensus']['accept_count']}/{result['consensus']['total_count']} methods agree")
        
        # Check all methods ran
        expected_methods = [
            'euclidean', 'manhattan', 'mahalanobis',
            'euclidean_iqr', 'euclidean_zscore', 'euclidean_iforest',
            'euclidean_robust', 'manhattan_robust', 'mahalanobis_robust'
        ]
        
        for method in expected_methods:
            if method in result['results'] and result['results'][method]:
                print(f"   ✓ {method}: score={result['results'][method]['score']:.4f}")
            else:
                print(f"   ✗ {method}: NOT FOUND")
        
        return True
        
    except Exception as e:
        print(f"❌ Comprehensive verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("\n" + "#"*60)
    print("#  COMPREHENSIVE VERIFICATION SYSTEM - TEST SUITE")
    print("#"*60)
    
    tests = [
        ("Imports", test_verifier_imports),
        ("Initialization", test_verifier_initialization),
        ("Outlier Methods", test_outlier_methods),
        ("Comprehensive Verification", test_comprehensive_verification)
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n❌ Test '{name}' crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}")
    
    print("\n" + "-"*60)
    print(f"Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! System is ready to use.")
        print("\nNext steps:")
        print("1. Install dependencies: pip install -r requirements.txt")
        print("2. Run Flask app: python webV2/app.py")
        print("3. Open browser: http://127.0.0.1:5000/login")
        print("4. Test verification mode with existing user")
    else:
        print("\n⚠️  Some tests failed. Please fix errors before deployment.")
        print("\nIf scikit-learn import failed, run:")
        print("   pip install scikit-learn")
    
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
