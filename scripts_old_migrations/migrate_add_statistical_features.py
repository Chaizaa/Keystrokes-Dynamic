"""
Migration Script: Add Statistical Features to Old Data
========================================================
This script updates biometric_auth.csv to add 'statistical_features' 
for all existing samples (221 rows) that don't have it yet.
"""

import csv
import json
import shutil
import os
from datetime import datetime

# Import verifier
import sys
sys.path.insert(0, 'webV2')
from verifier import Verifier

print("="*70)
print("📦 MIGRATION: Add Statistical Features to Old Data")
print("="*70)

# Paths
csv_path = "webV2/biometric_weak_auth.csv"
backup_path = f"webV2/biometric_weak_auth_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

# Step 1: Backup original file
print("\n1️⃣ Creating backup...")
if os.path.exists(csv_path):
    shutil.copy2(csv_path, backup_path)
    print(f"   ✅ Backup created: {backup_path}")
else:
    print(f"   ❌ CSV file not found: {csv_path}")
    exit(1)

# Step 2: Load all data
print("\n2️⃣ Loading data...")
with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    fieldnames = list(reader.fieldnames or [])

print(f"   ✅ Loaded {len(rows)} rows")
print(f"   Existing fields: {len(fieldnames)} columns")

# Remove None values from fieldnames if any
fieldnames = [f for f in fieldnames if f is not None]

# Step 3: Check if statistical_features already exists
if 'statistical_features' not in fieldnames:
    fieldnames.append('statistical_features')
    print(f"   ℹ️ Adding 'statistical_features' column")
else:
    print(f"   ℹ️ Column 'statistical_features' already exists")

# Step 4: Generate features for rows that don't have it
print("\n3️⃣ Generating statistical features...")
verifier = Verifier()
updated_count = 0
skipped_count = 0
error_count = 0

for i, row in enumerate(rows, 1):
    # Check if already has statistical_features
    if row.get('statistical_features') and row['statistical_features'].strip() not in ['', '[]', 'null']:
        skipped_count += 1
        continue
    
    try:
        # Parse vectors from JSON strings
        sample_dict = {
            'H_vector': json.loads(row.get('H_vector', '[]')),
            'DD_vector': json.loads(row.get('DD_vector', '[]')),
            'UD_vector': json.loads(row.get('UD_vector', '[]')),
            'UU_vector': json.loads(row.get('UU_vector', '[]')),
            'DU_vector': json.loads(row.get('DU_vector', '[]'))
        }
        
        # Generate statistical features
        features = verifier.extract_statistical_features(sample_dict)
        
        # Save as JSON string
        row['statistical_features'] = json.dumps(features.tolist())
        updated_count += 1
        
        if i % 50 == 0:
            print(f"   Progress: {i}/{len(rows)} rows processed...")
            
    except Exception as e:
        print(f"   ⚠️ Error on row {i} ({row.get('username', 'unknown')}): {e}")
        error_count += 1
        row['statistical_features'] = '[]'  # Empty array as fallback

# Step 5: Write back to CSV
print("\n4️⃣ Writing updated data...")

# Clean rows: remove any None keys
cleaned_rows = []
for row in rows:
    cleaned_row = {k: v for k, v in row.items() if k is not None}
    # Ensure all fieldnames are present
    for field in fieldnames:
        if field not in cleaned_row:
            cleaned_row[field] = ''
    cleaned_rows.append(cleaned_row)

with open(csv_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(cleaned_rows)

print(f"   ✅ Data written to {csv_path}")

# Step 6: Summary
print("\n" + "="*70)
print("📊 MIGRATION SUMMARY")
print("="*70)
print(f"Total rows:            {len(rows)}")
print(f"Updated with features: {updated_count}")
print(f"Already had features:  {skipped_count}")
print(f"Errors:                {error_count}")
print("")

if error_count == 0:
    print("✅ Migration completed successfully!")
else:
    print(f"⚠️ Migration completed with {error_count} errors")
    print("   Check the errors above and the data file")

print(f"\n💾 Backup saved at: {backup_path}")
print("   (Delete backup if migration looks good)")
print("="*70)

# Step 7: Verify a few samples
print("\n5️⃣ Verification (first 3 samples)...")
for i, row in enumerate(rows[:3], 1):
    username = row.get('username', 'unknown')
    stat_features = row.get('statistical_features', '')
    
    if stat_features and stat_features != '[]':
        features_array = json.loads(stat_features)
        print(f"   Sample {i} ({username}): {len(features_array)} features ✅")
    else:
        print(f"   Sample {i} ({username}): No features ❌")
