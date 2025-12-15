"""
Script untuk simulasi serangan: Login dengan password benar tapi pola waktu SALAH
"""
import sqlite3
import json
from verifier import Verifier

print("="*70)
print("SIMULASI: Attacker tahu password tapi ketik dengan pola waktu berbeda")
print("="*70)

# 1. Ambil profil enrollment user 'tes'
db_path = "biometric_auth.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("""
    SELECT * FROM user_vectors 
    WHERE username = 'tes' AND data_type = 'enrollment'
    ORDER BY id DESC LIMIT 10
""")

enrollment_data = [dict(row) for row in cursor.fetchall()]
conn.close()

if not enrollment_data:
    print("❌ User 'tes' tidak punya data enrollment!")
    exit(1)

print(f"\n✅ Ditemukan {len(enrollment_data)} sampel enrollment untuk user 'tes'")

# 2. Tampilkan profil asli
print("\n" + "-"*70)
print("PROFIL ASLI (dari enrollment):")
print("-"*70)

h_feat_orig = json.loads(enrollment_data[0]['H_features'])
print("H_features (waktu hold per karakter):")
for k, v in sorted(h_feat_orig.items()):
    print(f"  {k}: {v}s")

# 3. Buat simulasi input PALSU (password benar, waktu SALAH)
print("\n" + "-"*70)
print("SIMULASI INPUT ATTACKER:")
print("-"*70)
print("Attacker tahu password = 'test' tapi ketik cepat tanpa hold lama")
print("-"*70)

# Salin data asli tapi ubah waktu hold jadi super cepat
fake_input = dict(enrollment_data[0])

# Ubah semua hold time jadi 0.1 detik (ketik cepat)
h_feat_fake = {}
for k, v in h_feat_orig.items():
    # Jika aslinya >1 detik, ubah jadi 0.1 detik
    if v > 1.0:
        h_feat_fake[k] = 0.1  # BERBEDA DRASTIS!
        print(f"  {k}: {v}s → 0.1s (ANOMALY!)")
    else:
        h_feat_fake[k] = v

fake_input['H_features'] = json.dumps(h_feat_fake)
fake_input['DD_features'] = enrollment_data[0]['DD_features']
fake_input['UD_features'] = enrollment_data[0]['UD_features']

# Parse kembali untuk verifier
fake_input['H_features'] = json.loads(fake_input['H_features'])
fake_input['DD_features'] = json.loads(fake_input['DD_features'])
fake_input['UD_features'] = json.loads(fake_input['UD_features'])
fake_input['H_vector'] = json.loads(fake_input['H_vector'])
fake_input['DD_vector'] = json.loads(fake_input['DD_vector'])
fake_input['UD_vector'] = json.loads(fake_input['UD_vector'])
fake_input['UU_vector'] = json.loads(fake_input['UU_vector'])
fake_input['DU_vector'] = json.loads(fake_input['DU_vector'])

# 4. VERIFIKASI
print("\n" + "="*70)
print("HASIL VERIFIKASI:")
print("="*70)

verifier = Verifier()
result = verifier.verify_user(fake_input, enrollment_data)

print("\n" + "="*70)
if result['result']:
    print("❌ GAGAL! Attacker LOLOS meskipun pola waktu beda!")
    print(f"   Skor: {result['score']}, Threshold: {result['threshold']}")
else:
    print("✅ SUKSES! Attacker DITOLAK karena pola waktu tidak cocok!")
    print(f"   Reason: {result.get('reason', result.get('msg'))}")
print("="*70)
