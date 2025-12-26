import sqlite3

conn = sqlite3.connect('data/biometric_auth.db')
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

print("=== DATABASE SCHEMA ===\n")
for table in tables:
    table_name = table[0]
    print(f"\n📋 Table: {table_name}")
    print("=" * 60)
    
    # Get table schema
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    
    for col in columns:
        col_id, name, type_, not_null, default, pk = col
        constraints = []
        if pk:
            constraints.append("PRIMARY KEY")
        if not_null:
            constraints.append("NOT NULL")
        if default:
            constraints.append(f"DEFAULT {default}")
        
        constraint_str = f" ({', '.join(constraints)})" if constraints else ""
        print(f"  - {name}: {type_}{constraint_str}")

conn.close()
