"""
Script untuk melihat isi database dan mengecek filter data_type
"""
import sqlite3
import json

db_path = "biometric_auth.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("="*70)
print("CEK DATA DI DATABASE (FOKUS: data_type)")
print("="*70)

# 1. Lihat semua user dan data_type mereka
cursor.execute("""
    SELECT username, data_type, COUNT(*) as count 
    FROM user_vectors 
    GROUP BY username, data_type
    ORDER BY username
""")

rows = cursor.fetchall()

print("\n[RINGKASAN] User & Tipe Data:")
print("-"*70)
for row in rows:
    print(f"  User: {row['username']:15} | Type: {row['data_type']:20} | Count: {row['count']}")

print("\n" + "="*70)
print("CEK FILTER get_enrollment_samples()")
print("="*70)

# Test filter untuk user piqri
test_users = ['piqri', 'tes', 'tes1']

for username in test_users:
    print(f"\n[TEST] Username: {username}")
    
    # Query TANPA filter (seperti kode lama)
    cursor.execute("""
        SELECT COUNT(*) as total FROM user_vectors 
        WHERE username = ?
    """, (username,))
    total_all = cursor.fetchone()['total']
    
    # Query DENGAN filter enrollment (seperti kode baru)
    cursor.execute("""
        SELECT COUNT(*) as total FROM user_vectors 
        WHERE username = ? AND data_type = 'enrollment'
    """, (username,))
    total_enrollment = cursor.fetchone()['total']
    
    print(f"  - Total semua data    : {total_all}")
    print(f"  - Data enrollment only: {total_enrollment}")
    
    if total_enrollment > 0:
        # Ambil sample H_features
        cursor.execute("""
            SELECT H_features FROM user_vectors 
            WHERE username = ? AND data_type = 'enrollment'
            LIMIT 1
        """, (username,))
        
        sample = cursor.fetchone()
        if sample and sample['H_features']:
            h_feat = json.loads(sample['H_features'])
            print(f"  - Sample H_features (3 fitur pertama):")
            for i, (k, v) in enumerate(list(h_feat.items())[:3]):
                print(f"      {k}: {v}s")

conn.close()

print("\n" + "="*70)
print("KESIMPULAN:")
print("="*70)
print("Jika 'Data enrollment only' = 0, berarti semua data punya data_type salah!")
print("Solusi: Pastikan saat register, data_type = 'enrollment' disimpan dengan benar.")
print("="*70)
