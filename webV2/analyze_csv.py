import csv
from collections import Counter

# Load CSV
with open('biometric_auth.csv', 'r', encoding='utf-8') as f:
    data = list(csv.DictReader(f))

# Overall stats
print("=" * 70)
print("📊 BIOMETRIC_AUTH.CSV DATASET ANALYSIS")
print("=" * 70)
print(f"\n✅ Total Samples: {len(data)}")

# Data type breakdown
data_types = Counter([row.get('data_type', 'unknown') for row in data])
print(f"\n📁 Data Type Distribution:")
for dtype, count in data_types.items():
    print(f"   - {dtype:15s}: {count:3d} samples")

# Username breakdown
usernames = Counter([row['username'] for row in data])
print(f"\n👥 Total Users: {len(usernames)}")

# Per-user detail
users_detail = {}
for row in data:
    username = row['username']
    dtype = row.get('data_type', 'unknown')
    
    if username not in users_detail:
        users_detail[username] = {'enrollment': 0, 'login': 0}
    
    if dtype in users_detail[username]:
        users_detail[username][dtype] += 1

print(f"\n{'='*70}")
print("📋 PER-USER BREAKDOWN")
print(f"{'='*70}")
print(f"{'Username':<20} | {'Enrollment':^12} | {'Login':^12} | {'Status':^15}")
print("-" * 70)

for username in sorted(users_detail.keys()):
    stats = users_detail[username]
    enroll = stats.get('enrollment', 0)
    login = stats.get('login', 0)
    
    if enroll >= 10 and login >= 10:
        status = "✅ Complete"
    elif enroll >= 10:
        status = "⚠️ Login only"
    elif login > 0:
        status = "⚠️ Partial"
    else:
        status = "❌ Incomplete"
    
    print(f"{username:<20} | {enroll:2d}/10 ({enroll*10:3d}%) | {login:2d}/10 ({login*10:3d}%) | {status:^15}")

# Dataset quality check
print(f"\n{'='*70}")
print("🔍 DATASET QUALITY CHECK")
print(f"{'='*70}")

complete_users = sum(1 for u, s in users_detail.items() if s['enrollment'] >= 10 and s['login'] >= 10)
partial_users = sum(1 for u, s in users_detail.items() if s['enrollment'] >= 10 and s['login'] < 10)
incomplete_users = len(users_detail) - complete_users - partial_users

print(f"✅ Complete Users (10/10 + 10/10):  {complete_users}")
print(f"⚠️ Partial Users (10/10 + <10/10): {partial_users}")
print(f"❌ Incomplete Users:                {incomplete_users}")

# Check for collection mode data
collection_samples = [row for row in data if row.get('data_type') == 'login']
print(f"\n🎯 COLLECTION MODE DATA:")
print(f"   - Login samples collected: {len(collection_samples)}")
print(f"   - From {len(set(r['username'] for r in collection_samples))} different users")

if len(collection_samples) > 0:
    print(f"\n   ✅ Dataset INCLUDES Collection Mode data!")
    print(f"   📊 Ratio: {len(collection_samples)}/{len(data)} ({len(collection_samples)/len(data)*100:.1f}%)")
else:
    print(f"\n   ❌ Dataset DOES NOT include Collection Mode data!")

print(f"\n{'='*70}")
