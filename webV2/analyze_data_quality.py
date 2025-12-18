"""
Check data quality dan consistency
Usage: python analyze_data_quality.py
"""

import pandas as pd
import json
import numpy as np

def analyze_quality():
    df = pd.read_csv('biometric_auth.csv', on_bad_lines='skip', engine='python')
    df = df[df['data_type'] == 'enrollment']
    
    print("="*70)
    print("🔍 DATA QUALITY ANALYSIS")
    print("="*70)
    
    users = df['username'].unique()
    
    for username in sorted(users):
        user_df = df[df['username'] == username]
        
        print(f"\n{'─'*70}")
        print(f"👤 USER: {username.upper()}")
        print(f"{'─'*70}")
        print(f"Total samples: {len(user_df)}")
        
        # 1. Feature length consistency
        feature_lengths = []
        for idx, row in user_df.iterrows():
            try:
                H = json.loads(row['H_vector']) if isinstance(row['H_vector'], str) else []
                DD = json.loads(row['DD_vector']) if isinstance(row['DD_vector'], str) else []
                UD = json.loads(row['UD_vector']) if isinstance(row['UD_vector'], str) else []
                
                feat_len = len(H) + len(DD) + len(UD)
                feature_lengths.append(feat_len)
            except:
                feature_lengths.append(0)
        
        unique_lengths = set(feature_lengths)
        
        if len(unique_lengths) > 1:
            print(f"\n⚠️  INCONSISTENT FEATURE LENGTHS:")
            for length in unique_lengths:
                count = feature_lengths.count(length)
                print(f"   - Length {length}: {count} samples")
            print(f"   → PASSWORD BERUBAH-UBAH? Data corrupt!")
        else:
            print(f"\n✅ Feature length consistent: {list(unique_lengths)[0]}")
        
        # 2. Duration analysis
        durations = user_df['total_duration'].values
        
        print(f"\n⏱️  DURATION ANALYSIS:")
        print(f"   Min:      {durations.min():.2f}s")
        print(f"   Max:      {durations.max():.2f}s")
        print(f"   Mean:     {durations.mean():.2f}s")
        print(f"   Std Dev:  {durations.std():.2f}s")
        
        if durations.std() > 0.6:
            print(f"   ⚠️  HIGH VARIANCE! Typing speed tidak konsisten")
        
        # Check extremes
        too_fast = len(durations[durations < 1.0])
        too_slow = len(durations[durations > 4.0])
        
        if too_fast > 0:
            print(f"   ⚠️  {too_fast} samples TOO FAST (<1s) - Copy paste?")
        if too_slow > 0:
            print(f"   ⚠️  {too_slow} samples TOO SLOW (>4s) - Distracted?")
        
        # 3. Backspace analysis
        backspaces = user_df['backspace_count'].values
        
        print(f"\n⌫  BACKSPACE ANALYSIS:")
        print(f"   Total backspaces: {backspaces.sum()}")
        print(f"   Avg per sample:   {backspaces.mean():.1f}")
        print(f"   Max in 1 sample:  {backspaces.max()}")
        
        if backspaces.mean() > 1.5:
            print(f"   ⚠️  TOO MANY TYPOS! User tidak hafal password?")
        
        # 4. Recommendation
        print(f"\n💡 RECOMMENDATION FOR {username.upper()}:")
        
        issues = []
        if len(unique_lengths) > 1:
            issues.append("❌ Inconsistent feature length - PASSWORD CHANGED?")
        if durations.std() > 0.6:
            issues.append("❌ High variance - Type more consistently!")
        if too_fast > 2:
            issues.append("❌ Too many fast samples - NO COPY-PASTE!")
        if backspaces.mean() > 1.5:
            issues.append("❌ Too many typos - Practice typing!")
        
        if len(issues) == 0:
            print(f"   ✅ Data quality GOOD! Model should work.")
        else:
            print(f"   🚨 CRITICAL ISSUES:")
            for issue in issues:
                print(f"      {issue}")
            print(f"\n   → DELETE this user's data and RE-COLLECT!")

if __name__ == '__main__':
    analyze_quality()