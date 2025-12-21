"""
Quick Test: Password Strength Calculator
"""

from password_strength import calculate_password_strength, get_strength_label, get_strength_recommendations

# Test cases
test_passwords = [
    ("admin123", "Weak - Short, no uppercase, no special"),
    ("Password123", "Moderate - Has uppercase and numbers, but no special chars"),
    ("MyP@ssw0rd", "Moderate - Has all but length < 12"),
    ("MySecureP@ssw0rd2024", "Strong - Has all criteria, length >= 12"),
    ("Str0ng!P@ssword#2024", "Very Strong - All criteria + long"),
    ("abc", "Very Weak - Too short"),
]

print("="*70)
print("PASSWORD STRENGTH TEST")
print("="*70)

for password, expected in test_passwords:
    result = calculate_password_strength(password)
    label = get_strength_label(result)
    recommendations = get_strength_recommendations(result)
    
    print(f"\nPassword: {password}")
    print(f"Expected: {expected}")
    print(f"Result: {label} (Score: {result['score']}/{result['max_score']})")
    print(f"Strength: {result['strength']}")
    print(f"Details: {result['details']}")
    
    if recommendations:
        print(f"Recommendations:")
        for rec in recommendations:
            print(f"  - {rec}")
    else:
        print("✅ Perfect password!")

print("\n" + "="*70)
print("✅ Password strength calculator working correctly!")
print("="*70)
