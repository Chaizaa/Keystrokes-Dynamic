import sqlite3

conn = sqlite3.connect('biometric_auth.db')
cursor = conn.cursor()

try:
    # Check if timestamp column exists
    cursor.execute("PRAGMA table_info(user_vectors)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'timestamp' not in columns:
        print("Adding timestamp column to user_vectors...")
        # Add column without DEFAULT CURRENT_TIMESTAMP (not allowed in ALTER TABLE)
        cursor.execute("ALTER TABLE user_vectors ADD COLUMN timestamp TEXT")
        conn.commit()
        print("✅ timestamp column added successfully!")
    else:
        print("ℹ️  timestamp column already exists")
    
    # Also check password column
    if 'password' not in columns:
        print("Adding password column to user_vectors...")
        cursor.execute("ALTER TABLE user_vectors ADD COLUMN password TEXT")
        conn.commit()
        print("✅ password column added successfully!")
    else:
        print("ℹ️  password column already exists")
        
except Exception as e:
    print(f"❌ Error: {e}")
finally:
    conn.close()
