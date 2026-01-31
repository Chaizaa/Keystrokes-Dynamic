"""Simple password strength helpers used by API and tests.
This is a lightweight implementation to keep tests and app initialization working.
"""

from typing import Dict, List


def calculate_password_strength(password: str) -> Dict:
    if not password:
        return {"score": 0.0, "strength": "very weak"}
    score = min(1.0, max(0.0, len(password) / 12.0))
    if score >= 0.8:
        strength = "strong"
    elif score >= 0.5:
        strength = "medium"
    elif score >= 0.2:
        strength = "weak"
    else:
        strength = "very weak"
    return {"score": score, "strength": strength}


def get_strength_label(score: float) -> str:
    if score >= 0.8:
        return "Strong"
    if score >= 0.5:
        return "Medium"
    if score >= 0.2:
        return "Weak"
    return "Very Weak"


def get_strength_recommendations() -> List[str]:
    return [
        "Use at least 12 characters",
        "Mix uppercase, lowercase, numbers, and symbols",
        "Avoid common words and sequences",
    ]
