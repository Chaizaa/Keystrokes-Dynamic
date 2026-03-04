import csv
import json
from collections import Counter

import numpy as np

print("=" * 70)
print("🔍 ML TRAINING QUALITY CHECK - biometric_auth.csv")
print("=" * 70)

# Load data
with open("biometric_auth.csv", "r", encoding="utf-8") as f:
    data = list(csv.DictReader(f))

print(f"\n✅ Total Samples: {len(data)}")

# 1. Check for missing/empty values
print("\n" + "=" * 70)
print("1️⃣ MISSING VALUES CHECK")
print("=" * 70)

critical_fields = ["username", "H_vector", "DD_vector", "event_type"]
missing_count = {field: 0 for field in critical_fields}

for row in data:
    for field in critical_fields:
        if not row.get(field) or row.get(field).strip() == "":
            missing_count[field] += 1

has_missing = any(count > 0 for count in missing_count.values())
if has_missing:
    print("❌ FOUND MISSING VALUES:")
    for field, count in missing_count.items():
        if count > 0:
            print(f"   - {field}: {count} rows missing")
else:
    print("✅ No missing values in critical fields")

# 2. Check JSON parsing (vectors)
print("\n" + "=" * 70)
print("2️⃣ VECTOR FORMAT CHECK")
print("=" * 70)

parse_errors = {
    "H_vector": 0,
    "DD_vector": 0,
    "UD_vector": 0,
    "UU_vector": 0,
    "DU_vector": 0,
}
vector_lengths = {"H": [], "DD": [], "UD": [], "UU": [], "DU": []}

for i, row in enumerate(data):
    # Check H_vector
    try:
        h_vec = json.loads(row.get("H_vector", "[]"))
        if isinstance(h_vec, list):
            vector_lengths["H"].append(len(h_vec))
        else:
            parse_errors["H_vector"] += 1
    except:
        parse_errors["H_vector"] += 1

    # Check DD_vector
    try:
        dd_vec = json.loads(row.get("DD_vector", "[]"))
        if isinstance(dd_vec, list):
            vector_lengths["DD"].append(len(dd_vec))
        else:
            parse_errors["DD_vector"] += 1
    except:
        parse_errors["DD_vector"] += 1

    # Check other vectors
    for vec_name in ["UD_vector", "UU_vector", "DU_vector"]:
        try:
            vec = json.loads(row.get(vec_name, "[]"))
            key = vec_name.split("_")[0]
            if isinstance(vec, list):
                vector_lengths[key].append(len(vec))
            else:
                parse_errors[vec_name] += 1
        except:
            parse_errors[vec_name] += 1

has_parse_errors = any(count > 0 for count in parse_errors.values())
if has_parse_errors:
    print("❌ FOUND PARSING ERRORS:")
    for field, count in parse_errors.items():
        if count > 0:
            print(f"   - {field}: {count} rows corrupted")
else:
    print("✅ All vectors are valid JSON format")

# 3. Check vector length consistency
print("\n" + "=" * 70)
print("3️⃣ VECTOR LENGTH CONSISTENCY")
print("=" * 70)

for vec_type, lengths in vector_lengths.items():
    if lengths:
        length_distribution = Counter(lengths)
        most_common_length = length_distribution.most_common(1)[0][0]
        unique_lengths = len(length_distribution)

        if unique_lengths == 1:
            print(
                f"✅ {vec_type}_vector: All {len(lengths)} samples have length {most_common_length}"
            )
        else:
            print(f"⚠️ {vec_type}_vector: {unique_lengths} different lengths found!")
            print(f"   Distribution: {dict(length_distribution)}")
            print(
                f"   Most common: {most_common_length} ({length_distribution[most_common_length]} samples)"
            )

# 4. Check quality scores
print("\n" + "=" * 70)
print("4️⃣ QUALITY SCORE DISTRIBUTION")
print("=" * 70)

quality_scores = []
quality_labels = []

for row in data:
    try:
        score = float(row.get("quality_score", 0))
        quality_scores.append(score)
    except:
        pass

    label = row.get("quality_label", "unknown")
    quality_labels.append(label)

if quality_scores:
    print(f"Quality Scores (n={len(quality_scores)}):")
    print(f"   Mean:   {np.mean(quality_scores):.3f}")
    print(f"   Median: {np.median(quality_scores):.3f}")
    print(f"   Std:    {np.std(quality_scores):.3f}")
    print(f"   Min:    {np.min(quality_scores):.3f}")
    print(f"   Max:    {np.max(quality_scores):.3f}")

print(f"\nQuality Labels:")
label_dist = Counter(quality_labels)
for label, count in label_dist.most_common():
    pct = (count / len(quality_labels)) * 100
    print(f"   - {label:15s}: {count:3d} ({pct:5.1f}%)")

# 5. Check class balance (per user)
print("\n" + "=" * 70)
print("5️⃣ CLASS BALANCE FOR ML")
print("=" * 70)

# Per-user samples
user_samples = Counter([row["username"] for row in data])

# Filter complete users (>=10 enrollment + >=10 login)
complete_users = []
for username, total in user_samples.items():
    user_data = [r for r in data if r["username"] == username]
    enroll = sum(1 for r in user_data if r.get("event_type") == "enrollment")
    login = sum(1 for r in user_data if r.get("event_type") == "login")
    if enroll >= 10 and login >= 10:
        complete_users.append((username, enroll, login))

print(f"Complete users for ML: {len(complete_users)}")
if complete_users:
    enrolls = [e for _, e, _ in complete_users]
    logins = [l for _, _, l in complete_users]
    print(f"   Enrollment samples per user: {np.mean(enrolls):.1f} ± {np.std(enrolls):.1f}")
    print(f"   Login samples per user:      {np.mean(logins):.1f} ± {np.std(logins):.1f}")

    total_enroll = sum(enrolls)
    total_login = sum(logins)
    print(f"\n   Total usable for ML:")
    print(f"   - Enrollment (training): {total_enroll}")
    print(f"   - Login (testing):       {total_login}")
    print(f"   - Ratio: {total_login/total_enroll:.2f} (ideally ~1.0)")

# 6. Final verdict
print("\n" + "=" * 70)
print("📊 FINAL VERDICT FOR ML TRAINING")
print("=" * 70)

issues = []
warnings = []

if has_missing:
    issues.append("Missing values in critical fields")
if has_parse_errors:
    issues.append("Vector parsing errors (corrupted JSON)")
if len(complete_users) < 5:
    issues.append(f"Only {len(complete_users)} complete users (recommended: ≥10)")

# Check vector consistency
for vec_type, lengths in vector_lengths.items():
    if lengths:
        if len(Counter(lengths)) > 3:
            warnings.append(f"{vec_type}_vector has many different lengths (may need filtering)")

if quality_scores and np.std(quality_scores) > 0.3:
    warnings.append(f"High variance in quality scores (std={np.std(quality_scores):.3f})")

if issues:
    print("❌ CRITICAL ISSUES FOUND:")
    for i, issue in enumerate(issues, 1):
        print(f"   {i}. {issue}")
    print("\n⛔ Dataset NOT READY for ML training!")
elif warnings:
    print("⚠️ WARNINGS (not critical):")
    for i, warning in enumerate(warnings, 1):
        print(f"   {i}. {warning}")
    print("\n✅ Dataset is USABLE but consider fixing warnings")
else:
    print("✅ NO ISSUES FOUND!")
    print("✅ Dataset is READY for ML training!")
    print(f"\n📌 Recommended split:")
    print(f"   - Training: Enrollment samples ({total_enroll} samples)")
    print(f"   - Testing:  Login samples ({total_login} samples)")
    print(f"   - Users:    {len(complete_users)} complete users")

print("=" * 70)
