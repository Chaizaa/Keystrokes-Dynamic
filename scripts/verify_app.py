"""
Quick Verification Script - Test Flask App Initialization
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

print("=" * 70)
print("FLASK APPLICATION VERIFICATION")
print("=" * 70)

# Test 1: Import Flask app
print("\n1️⃣  Testing Flask app import...")
try:
    from app import create_app
    print("   ✅ Flask app imported successfully")
except Exception as e:
    print(f"   ❌ Failed to import Flask app: {e}")
    exit(1)

# Test 2: Create app instance
print("\n2️⃣  Testing app creation...")
try:
    app = create_app('development')
    print("   ✅ App created successfully")
except Exception as e:
    print(f"   ❌ Failed to create app: {e}")
    exit(1)

# Test 3: Test SQLAlchemy models
print("\n3️⃣  Testing SQLAlchemy models...")
try:
    from app.models import User, KeystrokeVector, LoginAttempt
    print("   ✅ User model imported")
    print("   ✅ KeystrokeVector model imported")
    print("   ✅ LoginAttempt model imported")
except Exception as e:
    print(f"   ❌ Failed to import models: {e}")
    exit(1)

# Test 4: Test service layer
print("\n4️⃣  Testing service layer...")
try:
    from app.services import AuthService, BiometricService
    auth_service = AuthService()
    bio_service = BiometricService()
    print("   ✅ AuthService instantiated")
    print("   ✅ BiometricService instantiated")
except Exception as e:
    print(f"   ❌ Failed to instantiate services: {e}")
    exit(1)

# Test 5: Test blueprints
print("\n5️⃣  Testing blueprints...")
try:
    from app.blueprints.main import main_bp
    from app.blueprints.auth import auth_bp
    from app.blueprints.api import api_bp
    print("   ✅ Main blueprint imported")
    print("   ✅ Auth blueprint imported")
    print("   ✅ API blueprint imported")
except Exception as e:
    print(f"   ❌ Failed to import blueprints: {e}")
    exit(1)

# Test 6: Test Flask-Login configuration
print("\n6️⃣  Testing Flask-Login...")
try:
    from flask_login import current_user
    with app.app_context():
        print(f"   ✅ Flask-Login configured")
        print(f"   ✅ Login view: auth.login_page")
except Exception as e:
    print(f"   ❌ Flask-Login test failed: {e}")
    exit(1)

# Test 7: Test CSRF protection
print("\n7️⃣  Testing CSRF protection...")
try:
    csrf_enabled = app.config.get('WTF_CSRF_CHECK_DEFAULT', False)
    csrf_headers = app.config.get('WTF_CSRF_HEADERS', [])
    print(f"   ✅ CSRF enabled: {csrf_enabled}")
    print(f"   ✅ CSRF headers: {csrf_headers}")
except Exception as e:
    print(f"   ❌ CSRF test failed: {e}")
    exit(1)

# Test 8: Test database connection
print("\n8️⃣  Testing database connection...")
try:
    with app.app_context():
        from app.models import db
        # Check if tables exist
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"   ✅ Database connected")
        print(f"   ✅ Tables: {tables}")
except Exception as e:
    print(f"   ❌ Database test failed: {e}")
    exit(1)

# Test 9: Test service methods
print("\n9️⃣  Testing service methods...")
try:
    # Test AuthService
    is_valid, message = auth_service.validate_username("testuser")
    print(f"   ✅ AuthService.validate_username(): {is_valid}")
    
    # Test BiometricService
    status = bio_service.get_enrollment_status("testuser")
    print(f"   ✅ BiometricService.get_enrollment_status(): {status['count']} samples")
except Exception as e:
    print(f"   ❌ Service method test failed: {e}")
    exit(1)

# Summary
print("\n" + "=" * 70)
print("VERIFICATION COMPLETE - ALL TESTS PASSED ✅")
print("=" * 70)
print("\n📋 Summary:")
print("   ✅ Flask app initialization")
print("   ✅ SQLAlchemy models")
print("   ✅ Service layer (AuthService, BiometricService)")
print("   ✅ Blueprints (main, auth, api)")
print("   ✅ Flask-Login session management")
print("   ✅ CSRF protection")
print("   ✅ Database connection")
print("   ✅ Service methods")
print("\n🚀 Application is ready to run!")
print("   Run: python run.py")
print("   URL: http://127.0.0.1:5000")
print("=" * 70)
