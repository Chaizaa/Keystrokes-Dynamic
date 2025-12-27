"""
Data Migration Script - Migrate old database data to new SQLAlchemy models
"""
import sqlite3
import json
from datetime import datetime
import sys
sys.path.insert(0, '.')

from app import create_app
from app.models import db, User, KeystrokeVector, LoginAttempt

def parse_json_field(value):
    """Safely parse JSON field from database"""
    if value is None:
        return None
    try:
        return json.loads(value) if isinstance(value, str) else value
    except:
        return None

def migrate_data():
    """Migrate data from old schema to SQLAlchemy models"""
    
    app = create_app('development')
    
    with app.app_context():
        print("=" * 70)
        print("DATABASE MIGRATION - Old Schema → SQLAlchemy Models")
        print("=" * 70)
        
        # Connect to current database (already has data)
        db_path = 'data/biometric_auth.db'
        
        print(f"\n📂 Checking current database: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. Check Users already migrated
        print("\n1️⃣  Checking Users...")
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"   Found {user_count} users in database")
        
        from sqlalchemy import select, func
        existing_users = int(db.session.execute(select(func.count()).select_from(User)).scalar_one())
        print(f"   SQLAlchemy User model has {existing_users} users")
        
        if existing_users == 0 and user_count > 0:
            print("   ⚠️  Users not in SQLAlchemy! Need to sync...")
            cursor.execute("SELECT * FROM users")
            users_data = cursor.fetchall()
            
            for user_row in users_data:
                # Schema: id, username, plain_password, password_hash, created_at, updated_at
                user_id, username, plain_pass, pass_hash, created_at, updated_at = user_row
                
                new_user = User()
                new_user.id = user_id  # Keep original ID
                new_user.username = username
                new_user.plain_password = plain_pass
                new_user.password_hash = pass_hash
                new_user.created_at = datetime.fromisoformat(created_at) if created_at else datetime.utcnow()
                new_user.updated_at = datetime.fromisoformat(updated_at) if updated_at else None
                
                db.session.add(new_user)
                print(f"   ✅ Synced: {username} (ID: {user_id})")
            
            db.session.commit()
            print(f"   💾 Committed {len(users_data)} users")
        else:
            print("   ✅ Users already synced!")
        
        # 2. Migrate Keystroke Vectors
        print("\n2️⃣  Migrating Keystroke Vectors...")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_vectors'")
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) FROM user_vectors")
            count = cursor.fetchone()[0]
            print(f"   Found {count} keystroke vectors")
            
            existing_vectors = int(db.session.execute(select(func.count()).select_from(KeystrokeVector)).scalar_one())
            print(f"   SQLAlchemy KeystrokeVector model has {existing_vectors} vectors")
            
            if existing_vectors == 0 and count > 0:
                print("   ⚠️  Vectors not in SQLAlchemy! Migrating...")
                
                cursor.execute("SELECT * FROM user_vectors")
                vectors_data = cursor.fetchall()
                
                # Column names
                cols = ['id', 'user_id', 'username', 'event_type', 'is_successful', 'timestamp',
                       'password', 'password_hash', 'H_vector', 'DD_vector', 'UD_vector', 
                       'UU_vector', 'DU_vector', 'H_features', 'DD_features', 'UD_features',
                       'UU_features', 'DU_features', 'mean_H', 'std_H', 'mean_DD', 'std_DD',
                       'mean_UD', 'std_UD', 'skew_H', 'kurtosis_H', 'median_H', 'iqr_H',
                       'sample_quality', 'quality_warnings', 'password_strength', 
                       'password_score', 'raw_events', 'session_id']
                
                migrated = 0
                for vector_row in vectors_data:
                    vector_dict = dict(zip(cols, vector_row))
                    
                    new_vector = KeystrokeVector()
                    new_vector.id = vector_dict['id']
                    new_vector.user_id = vector_dict['user_id']
                    new_vector.username = vector_dict['username']
                    new_vector.event_type = vector_dict['event_type']
                    new_vector.is_successful = vector_dict['is_successful']
                    new_vector.timestamp = datetime.fromisoformat(vector_dict['timestamp'])
                    new_vector.password = vector_dict['password']
                    new_vector.password_hash = vector_dict['password_hash']
                    
                    # JSON fields
                    new_vector.H_vector = vector_dict['H_vector']
                    new_vector.DD_vector = vector_dict['DD_vector']
                    new_vector.UD_vector = vector_dict['UD_vector']
                    new_vector.UU_vector = vector_dict['UU_vector']
                    new_vector.DU_vector = vector_dict['DU_vector']
                    
                    new_vector.H_features = vector_dict['H_features']
                    new_vector.DD_features = vector_dict['DD_features']
                    new_vector.UD_features = vector_dict['UD_features']
                    new_vector.UU_features = vector_dict['UU_features']
                    new_vector.DU_features = vector_dict['DU_features']
                    
                    # Statistics
                    new_vector.mean_H = vector_dict['mean_H']
                    new_vector.std_H = vector_dict['std_H']
                    new_vector.mean_DD = vector_dict['mean_DD']
                    new_vector.std_DD = vector_dict['std_DD']
                    new_vector.mean_UD = vector_dict['mean_UD']
                    new_vector.std_UD = vector_dict['std_UD']
                    new_vector.skew_H = vector_dict['skew_H']
                    new_vector.kurtosis_H = vector_dict['kurtosis_H']
                    new_vector.median_H = vector_dict['median_H']
                    new_vector.iqr_H = vector_dict['iqr_H']
                    
                    # Quality & metadata
                    new_vector.sample_quality = vector_dict['sample_quality']
                    new_vector.quality_warnings = vector_dict['quality_warnings']
                    new_vector.password_strength = vector_dict['password_strength']
                    new_vector.password_score = vector_dict['password_score']
                    new_vector.raw_events = vector_dict['raw_events']
                    new_vector.session_id = vector_dict['session_id']
                    
                    db.session.add(new_vector)
                    migrated += 1
                    
                    if migrated % 100 == 0:
                        db.session.commit()
                        print(f"   💾 Committed {migrated} vectors...")
                
                db.session.commit()
                print(f"   ✅ Migrated {migrated} keystroke vectors")
            else:
                print("   ✅ Vectors already migrated!")
        else:
            print("   ℹ️  Table 'user_vectors' not found")
        
        # 3. Migrate Login Attempts
        print("\n3️⃣  Migrating Login Attempts...")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='login_attempts'")
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) FROM login_attempts")
            count = cursor.fetchone()[0]
            print(f"   Found {count} login attempts")
            
            existing_attempts = int(db.session.execute(select(func.count()).select_from(LoginAttempt)).scalar_one())
            print(f"   SQLAlchemy LoginAttempt model has {existing_attempts} attempts")
            
            if existing_attempts == 0 and count > 0:
                print("   ⚠️  Login attempts not in SQLAlchemy! Migrating...")
                
                cursor.execute("SELECT * FROM login_attempts")
                attempts_data = cursor.fetchall()
                
                cols = ['id', 'user_id', 'username', 'success', 'failure_reason',
                       'verification_score', 'verification_method', 'biometric_tier',
                       'ip_address', 'user_agent', 'timestamp', 'session_id',
                       'attempts_in_window', 'rate_limit_hit']
                
                migrated = 0
                for attempt_row in attempts_data:
                    attempt_dict = dict(zip(cols, attempt_row))
                    
                    new_attempt = LoginAttempt()
                    new_attempt.id = attempt_dict['id']
                    new_attempt.user_id = attempt_dict['user_id']
                    new_attempt.username = attempt_dict['username']
                    new_attempt.success = attempt_dict['success']
                    new_attempt.failure_reason = attempt_dict['failure_reason']
                    new_attempt.verification_score = attempt_dict['verification_score']
                    new_attempt.verification_method = attempt_dict['verification_method']
                    new_attempt.biometric_tier = attempt_dict['biometric_tier']
                    new_attempt.ip_address = attempt_dict['ip_address']
                    new_attempt.user_agent = attempt_dict['user_agent']
                    new_attempt.timestamp = datetime.fromisoformat(attempt_dict['timestamp'])
                    new_attempt.session_id = attempt_dict['session_id']
                    new_attempt.attempts_in_window = attempt_dict['attempts_in_window']
                    new_attempt.rate_limit_hit = attempt_dict['rate_limit_hit']
                    
                    db.session.add(new_attempt)
                    migrated += 1
                    
                    if migrated % 100 == 0:
                        db.session.commit()
                        print(f"   💾 Committed {migrated} attempts...")
                
                db.session.commit()
                print(f"   ✅ Migrated {migrated} login attempts")
            else:
                print("   ✅ Login attempts already migrated!")
        else:
            print("   ℹ️  Table 'login_attempts' not found")
        
        conn.close()
        
        # 4. Verify migration
        print("\n4️⃣  Verification:")
        user_count = int(db.session.execute(select(func.count()).select_from(User)).scalar_one())
        vector_count = int(db.session.execute(select(func.count()).select_from(KeystrokeVector)).scalar_one())
        attempt_count = int(db.session.execute(select(func.count()).select_from(LoginAttempt)).scalar_one())
        
        print(f"   Users: {user_count}")
        print(f"   Keystroke Vectors: {vector_count}")
        print(f"   Login Attempts: {attempt_count}")
        
        # Show sample
        if user_count > 0:
            sample_user = db.session.execute(select(User)).scalars().first()
            print(f"\n   Sample User: {sample_user.username} (ID: {sample_user.id})")
            print(f"   - Enrollment samples: {sample_user.get_enrollment_count()}")
        
        print("\n✅ Migration Complete!")
        print("=" * 70)

if __name__ == '__main__':
    migrate_data()
