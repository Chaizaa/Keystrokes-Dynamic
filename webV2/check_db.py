import sqlite3
import json

conn = sqlite3.connect('biometric_auth.db')
cursor = conn.cursor()

# Ambil 5 data terakhir
cursor.execute("""
    SELECT id, username, timestamp, char_sequence, H_features, total_duration
    FROM user_vectors 
    ORDER BY id DESC 
    LIMIT 5
""")

rows = cursor.fetchall()

print("\n" + "="*80)
print("ISI DATABASE (5 Data Terakhir)")
print("="*80)

for row in rows:
    row_id, username, timestamp, char_seq, h_feat, duration = row
    
    print(f"\n[ID {row_id}] User: {username} | Time: {timestamp}")
    print(f"Duration: {duration}s")
    
    # Parse char_sequence
    try:
        chars = json.loads(char_seq) if isinstance(char_seq, str) else char_seq
        print(f"Char Sequence: {chars}")
    except:
        print(f"Char Sequence (raw): {char_seq}")
    
    # Parse H_features
    try:
        h_dict = json.loads(h_feat) if isinstance(h_feat, str) else h_feat
        print(f"H_features:")
        for key, val in h_dict.items():
            print(f"  {key}: {val}")
    except Exception as e:
        print(f"H_features (raw): {h_feat}")
    
    print("-" * 80)

conn.close()
print("\n✅ Selesai!")
