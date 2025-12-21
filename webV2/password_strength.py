"""
Password Strength Calculator
Classifies passwords as 'strong' or 'weak' based on security criteria
"""

def calculate_password_strength(password):
    """
    Classify password as 'strong' or 'weak' based on security criteria.
    
    Strong password criteria:
    - Length >= 12 characters
    - Has uppercase letters
    - Has lowercase letters
    - Has numbers
    - Has special characters
    
    Args:
        password (str): The password to evaluate
        
    Returns:
        dict: {
            'strength': 'strong' or 'weak',
            'score': int (0-6),
            'details': dict with criteria results
        }
    """
    if not password:
        return {'strength': 'weak', 'score': 0, 'details': {}}
    
    score = 0
    details = {}
    
    # Length check
    length = len(password)
    if length >= 12:
        score += 2
        details['length'] = 'excellent (>=12)'
    elif length >= 8:
        score += 1
        details['length'] = 'good (8-11)'
    else:
        details['length'] = 'weak (<8)'
    
    # Uppercase check
    has_upper = any(c.isupper() for c in password)
    if has_upper:
        score += 1
        details['uppercase'] = 'yes'
    else:
        details['uppercase'] = 'no'
    
    # Lowercase check
    has_lower = any(c.islower() for c in password)
    if has_lower:
        score += 1
        details['lowercase'] = 'yes'
    else:
        details['lowercase'] = 'no'
    
    # Numbers check
    has_digit = any(c.isdigit() for c in password)
    if has_digit:
        score += 1
        details['numbers'] = 'yes'
    else:
        details['numbers'] = 'no'
    
    # Special characters check
    special_chars = '!@#$%^&*()_+-=[]{}|;:,.<>?/~`'
    has_special = any(c in special_chars for c in password)
    if has_special:
        score += 1
        details['special_chars'] = 'yes'
    else:
        details['special_chars'] = 'no'
    
    # Classification
    # Strong: score >= 5 (e.g., 12+ chars + 3 criteria OR 8+ chars + 4 criteria)
    # Weak: score < 5
    strength = 'strong' if score >= 5 else 'weak'
    
    return {
        'strength': strength,
        'score': score,
        'max_score': 6,
        'details': details
    }


def get_strength_label(strength_result):
    """Get user-friendly label for password strength"""
    strength = strength_result['strength']
    score = strength_result['score']
    
    if strength == 'strong':
        if score == 6:
            return "🔒 Very Strong"
        else:
            return "✅ Strong"
    else:
        if score >= 3:
            return "⚠️ Moderate"
        else:
            return "❌ Weak"


def get_strength_recommendations(strength_result):
    """Get recommendations to improve password strength"""
    details = strength_result['details']
    recommendations = []
    
    if 'weak' in details.get('length', ''):
        recommendations.append("Use at least 8 characters (12+ recommended)")
    elif 'good' in details.get('length', ''):
        recommendations.append("Consider using 12+ characters for better security")
    
    if details.get('uppercase') == 'no':
        recommendations.append("Add uppercase letters (A-Z)")
    
    if details.get('lowercase') == 'no':
        recommendations.append("Add lowercase letters (a-z)")
    
    if details.get('numbers') == 'no':
        recommendations.append("Add numbers (0-9)")
    
    if details.get('special_chars') == 'no':
        recommendations.append("Add special characters (!@#$%^&*)")
    
    return recommendations
