"""
Script untuk testing verifikasi biometrik - ANALISIS DETAIL
Menganalisis kenapa login gagal dan di bagian mana pola waktu tidak cocok
"""
import sys
import json
import numpy as np
from db import Database
from verifier import Verifier

db_manager = Database(
    db_name="biometric_auth.db",
    csv_name="biometric_auth.csv"
)
verifier = Verifier()

# Test dengan user tes
username = "tes"

print("="*80)
print(f"ANALISIS VERIFIKASI GAGAL UNTUK USER: {username}")
print("="*80)

# 1. Ambil data enrollment
enrollment_data = db_manager.get_enrollment_samples(username)

if not enrollment_data:
    print(f"❌ User '{username}' tidak ditemukan atau belum ada data enrollment!")
    sys.exit(1)

print(f"\n✅ Ditemukan {len(enrollment_data)} sampel enrollment")

# 2. Ambil data login attempt yang gagal
import sqlite3
conn = sqlite3.connect("biometric_auth.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("""
    SELECT * FROM user_vectors 
    WHERE username = ? AND data_type = 'login_attempt'
    ORDER BY id DESC LIMIT 1
""", (username,))

login_attempt = cursor.fetchone()
conn.close()

if not login_attempt:
    print(f"\n❌ Tidak ada login attempt yang gagal untuk user '{username}'")
    print("Lakukan login terlebih dahulu di browser!")
    sys.exit(1)

login_attempt = dict(login_attempt)
print(f"✅ Ditemukan login attempt: {login_attempt['timestamp']}")
print(f"   Result: {login_attempt.get('login_result', 'N/A')}")
print(f"   Score: {login_attempt.get('login_score', 'N/A')}")

# 3. BANGUN PROFIL RATA-RATA dari enrollment
print("\n" + "="*80)
print("MEMBUAT PROFIL RATA-RATA DARI ENROLLMENT")
print("="*80)

h_features_list = []
dd_features_list = []
ud_features_list = []

for sample in enrollment_data:
    h_feat = json.loads(sample['H_features']) if isinstance(sample['H_features'], str) else sample['H_features']
    dd_feat = json.loads(sample['DD_features']) if isinstance(sample['DD_features'], str) else sample['DD_features']
    ud_feat = json.loads(sample['UD_features']) if isinstance(sample['UD_features'], str) else sample['UD_features']
    
    h_features_list.append(h_feat)
    dd_features_list.append(dd_feat)
    ud_features_list.append(ud_feat)

# Hitung rata-rata untuk setiap fitur
h_profile = {}
for key in h_features_list[0].keys():
    values = [f[key] for f in h_features_list if key in f]
    h_profile[key] = np.mean(values)

dd_profile = {}
for key in dd_features_list[0].keys():
    values = [f[key] for f in dd_features_list if key in f]
    dd_profile[key] = np.mean(values)

ud_profile = {}
for key in ud_features_list[0].keys():
    values = [f[key] for f in ud_features_list if key in f]
    ud_profile[key] = np.mean(values)

print(f"\nProfil H_features (rata-rata dari {len(enrollment_data)} sampel):")
for key, value in sorted(h_profile.items()):
    print(f"  {key}: {value:.4f}s")

# 4. BANDINGKAN dengan LOGIN ATTEMPT
print("\n" + "="*80)
print("PERBANDINGAN: PROFIL vs LOGIN ATTEMPT")
print("="*80)

login_h = json.loads(login_attempt['H_features']) if isinstance(login_attempt['H_features'], str) else login_attempt['H_features']
login_dd = json.loads(login_attempt['DD_features']) if isinstance(login_attempt['DD_features'], str) else login_attempt['DD_features']
login_ud = json.loads(login_attempt['UD_features']) if isinstance(login_attempt['UD_features'], str) else login_attempt['UD_features']

print("\n📊 H_FEATURES (Hold Time per Karakter):")
print("-" * 80)
print(f"{'Fitur':<15} {'Profil (s)':<12} {'Login (s)':<12} {'Diff (s)':<12} {'Status'}")
print("-" * 80)

extreme_anomalies = []
for key in sorted(h_profile.keys()):
    profile_val = h_profile[key]
    login_val = login_h.get(key, 0)
    diff = abs(profile_val - login_val)
    
    status = "✅ OK"
    if diff > 0.5:
        status = "⚠️ EXTREME!"
        extreme_anomalies.append((key, profile_val, login_val, diff))
    elif diff > 0.2:
        status = "⚠️ High"
    
    print(f"{key:<15} {profile_val:<12.4f} {login_val:<12.4f} {diff:<12.4f} {status}")

print("\n📊 DD_FEATURES (Down-Down Interval):")
print("-" * 80)
print(f"{'Fitur':<20} {'Profil (s)':<12} {'Login (s)':<12} {'Diff (s)':<12} {'Status'}")
print("-" * 80)

for key in sorted(dd_profile.keys()):
    profile_val = dd_profile[key]
    login_val = login_dd.get(key, 0)
    diff = abs(profile_val - login_val)
    
    status = "✅ OK"
    if diff > 0.5:
        status = "⚠️ EXTREME!"
        extreme_anomalies.append((key, profile_val, login_val, diff))
    elif diff > 0.2:
        status = "⚠️ High"
    
    print(f"{key:<20} {profile_val:<12.4f} {login_val:<12.4f} {diff:<12.4f} {status}")

print("\n📊 UD_FEATURES (Up-Down Interval):")
print("-" * 80)
print(f"{'Fitur':<20} {'Profil (s)':<12} {'Login (s)':<12} {'Diff (s)':<12} {'Status'}")
print("-" * 80)

for key in sorted(ud_profile.keys()):
    profile_val = ud_profile[key]
    login_val = login_ud.get(key, 0)
    diff = abs(profile_val - login_val)
    
    status = "✅ OK"
    if diff > 0.5:
        status = "⚠️ EXTREME!"
        extreme_anomalies.append((key, profile_val, login_val, diff))
    elif diff > 0.2:
        status = "⚠️ High"
    
    print(f"{key:<20} {profile_val:<12.4f} {login_val:<12.4f} {diff:<12.4f} {status}")

# 5. KESIMPULAN
print("\n" + "="*80)
print("KESIMPULAN ANALISIS")
print("="*80)

if extreme_anomalies:
    print(f"\n❌ DITEMUKAN {len(extreme_anomalies)} ANOMALY EKSTREM (Diff >0.5s):")
    print("-" * 80)
    for feature, prof, login_val, diff in extreme_anomalies:
        print(f"\n  Fitur: {feature}")
        print(f"  └─ Profil : {prof:.4f}s")
        print(f"  └─ Login  : {login_val:.4f}s")
        print(f"  └─ Diff   : {diff:.4f}s ⚠️")
        
        # Interpretasi
        if 'H.' in feature:
            char = feature.split('.')[1].split('_')[0]
            print(f"  └─ Artinya: Waktu HOLD karakter '{char}' berbeda {diff:.2f} detik!")
        elif 'DD.' in feature:
            chars = feature.replace('DD.', '').replace('_', ' → ')
            print(f"  └─ Artinya: Interval DOWN-DOWN {chars} berbeda {diff:.2f} detik!")
        elif 'UD.' in feature:
            chars = feature.replace('UD.', '').replace('_', ' → ')
            print(f"  └─ Artinya: Interval UP-DOWN {chars} berbeda {diff:.2f} detik!")
    
    print("\n" + "-" * 80)
    print("💡 ALASAN LOGIN DITOLAK:")
    print("   Sistem mendeteksi perbedaan ekstrem (>0.5s) pada pola waktu ketikan.")
    print("   Ini menandakan bahwa cara mengetik password BERBEDA dari profil asli.")
    print("="*80)
else:
    print("\n✅ TIDAK ADA ANOMALY EKSTREM")
    print("   Login seharusnya LOLOS jika skor di bawah threshold 0.30")
    print("="*80)
