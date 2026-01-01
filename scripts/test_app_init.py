"""
Test app initialization with SQLAlchemy
"""

import sys

sys.path.insert(0, ".")

try:
    from app import create_app

    print("✅ Import successful")

    app = create_app("development")
    print("✅ App created successfully!")

    with app.app_context():
        from app.models import KeystrokeVector, LoginAttempt, User, db

        print(f"✅ Models imported: User, KeystrokeVector, LoginAttempt")
        print(f"✅ Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
