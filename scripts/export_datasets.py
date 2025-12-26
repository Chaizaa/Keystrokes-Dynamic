"""
Dataset Export Script for ML Training
Splits biometric_auth.csv into strong and weak password datasets
"""

import pandas as pd
import os
from datetime import datetime

def export_datasets():
    """Export datasets split by password strength"""
    
    # Paths
    main_csv = 'biometric_auth.csv'
    datasets_dir = 'datasets'
    strong_csv = os.path.join(datasets_dir, 'strong_passwords.csv')
    weak_csv = os.path.join(datasets_dir, 'weak_passwords.csv')
    
    # Create datasets directory if not exists
    os.makedirs(datasets_dir, exist_ok=True)
    
    # Check if main CSV exists
    if not os.path.exists(main_csv):
        print(f"❌ Error: {main_csv} not found!")
        print(f"   Current directory: {os.getcwd()}")
        return
    
    print(f"📊 Reading {main_csv}...")
    df = pd.read_csv(main_csv)
    
    # Check if password_strength column exists
    if 'password_strength' not in df.columns:
        print(f"⚠️ Warning: 'password_strength' column not found!")
        print(f"   Available columns: {list(df.columns)}")
        print(f"\n   This might be old data. Run migration script first.")
        return
    
    # Filter by password strength
    df_strong = df[df['password_strength'] == 'strong'].copy()
    df_weak = df[df['password_strength'] == 'weak'].copy()
    df_unknown = df[df['password_strength'].isin(['unknown', 'Unknown'])].copy()
    
    # Export strong passwords
    if len(df_strong) > 0:
        df_strong.to_csv(strong_csv, index=False)
        print(f"✅ Exported {len(df_strong)} strong password samples to {strong_csv}")
    else:
        print(f"⚠️ No strong password samples found")
    
    # Export weak passwords
    if len(df_weak) > 0:
        df_weak.to_csv(weak_csv, index=False)
        print(f"✅ Exported {len(df_weak)} weak password samples to {weak_csv}")
    else:
        print(f"⚠️ No weak password samples found")
    
    # Statistics
    print(f"\n{'='*60}")
    print(f"📈 DATASET STATISTICS")
    print(f"{'='*60}")
    print(f"Total samples:    {len(df):>6}")
    print(f"Strong passwords: {len(df_strong):>6} ({len(df_strong)/len(df)*100:.1f}%)")
    print(f"Weak passwords:   {len(df_weak):>6} ({len(df_weak)/len(df)*100:.1f}%)")
    if len(df_unknown) > 0:
        print(f"Unknown:          {len(df_unknown):>6} ({len(df_unknown)/len(df)*100:.1f}%)")
    print(f"{'='*60}")
    
    # User distribution
    print(f"\n📊 USER DISTRIBUTION:")
    print(f"\nStrong passwords:")
    if len(df_strong) > 0:
        strong_users = df_strong.groupby('username').size().sort_values(ascending=False)
        for user, count in strong_users.items():
            print(f"  - {user}: {count} samples")
    else:
        print(f"  (none)")
    
    print(f"\nWeak passwords:")
    if len(df_weak) > 0:
        weak_users = df_weak.groupby('username').size().sort_values(ascending=False)
        for user, count in weak_users.items():
            print(f"  - {user}: {count} samples")
    else:
        print(f"  (none)")
    
    # Data type distribution
    print(f"\n📊 DATA TYPE DISTRIBUTION:")
    print(f"\nStrong passwords:")
    if len(df_strong) > 0:
        strong_types = df_strong['data_type'].value_counts()
        for dtype, count in strong_types.items():
            print(f"  - {dtype}: {count} samples")
    
    print(f"\nWeak passwords:")
    if len(df_weak) > 0:
        weak_types = df_weak['data_type'].value_counts()
        for dtype, count in weak_types.items():
            print(f"  - {dtype}: {count} samples")
    
    # Export summary
    summary = {
        'export_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_samples': len(df),
        'strong_samples': len(df_strong),
        'weak_samples': len(df_weak),
        'unknown_samples': len(df_unknown),
        'strong_percentage': f"{len(df_strong)/len(df)*100:.1f}%" if len(df) > 0 else "0%",
        'weak_percentage': f"{len(df_weak)/len(df)*100:.1f}%" if len(df) > 0 else "0%"
    }
    
    summary_file = os.path.join(datasets_dir, 'export_summary.txt')
    with open(summary_file, 'w') as f:
        f.write(f"Dataset Export Summary\n")
        f.write(f"{'='*60}\n")
        for key, value in summary.items():
            f.write(f"{key}: {value}\n")
    
    print(f"\n✅ Summary saved to {summary_file}")
    print(f"✅ Export complete!")


if __name__ == '__main__':
    print(f"🚀 Starting dataset export...")
    print(f"   Working directory: {os.getcwd()}")
    export_datasets()
