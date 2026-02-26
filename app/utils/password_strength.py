"""Password strength evaluator.

Scores passwords based on five independent criteria:
  - Length             (0.00 – 0.35, progressive)
  - Uppercase letters  (+0.15)
  - Lowercase letters  (+0.15)
  - Digits             (+0.15)
  - Special characters (+0.20)

The returned ``score`` is a float in **[0.0, 1.0]**.

Strength thresholds
-------------------
  score in [0.00, 0.33]  →  "very_weak"
  score in [0.34, 0.50]  →  "weak"
  score in [0.51, 0.66]  →  "medium"
  score in [0.67, 1.00]  →  "strong"
"""

import string
from typing import Dict, List

# All punctuation characters count as "special"
_SPECIAL_CHARS: frozenset = frozenset(string.punctuation)

# (detail_key, human label, weight, test_function)
_CHAR_CRITERIA = (
    ("has_uppercase", "Uppercase letter (A–Z)",    0.15, lambda p: any(c.isupper() for c in p)),
    ("has_lowercase", "Lowercase letter (a–z)",    0.15, lambda p: any(c.islower() for c in p)),
    ("has_digit",     "Number (0–9)",              0.15, lambda p: any(c.isdigit() for c in p)),
    ("has_special",   "Special character (!@#$…)", 0.20, lambda p: any(c in _SPECIAL_CHARS for c in p)),
)


def _length_score(password: str) -> tuple:
    """Return (weight, description) for the length criterion."""
    n = len(password)
    if n >= 16:
        return 0.35, f"excellent (≥16, got {n})"
    if n >= 12:
        return 0.30, f"great (12–15, got {n})"
    if n >= 8:
        return 0.20, f"good (8–11, got {n})"
    if n >= 4:
        return 0.10, f"short (4–7, got {n})"
    return 0.00, f"too short (<4, got {n})"


def calculate_password_strength(password: str) -> Dict:
    """
    Evaluate password strength based on multiple security criteria.

    Args:
        password: Plain-text password to evaluate.

    Returns:
        dict with keys:
          - score (float 0.0–1.0): normalized strength score
          - strength (str): one of ``'very_weak'``, ``'weak'``, ``'medium'``, ``'strong'``
          - details (dict): per-criterion breakdown {key: {label, pass, ...}}
          - recommendations (list[str]): actionable improvement hints
    """
    if not password:
        return {
            "score": 0.0,
            "strength": "very_weak",
            "details": {},
            "recommendations": _generic_recommendations(),
        }

    details: Dict[str, Dict] = {}
    score: float = 0.0

    # --- Length ---
    length_weight, length_desc = _length_score(password)
    score += length_weight
    details["length"] = {
        "label": f"Length: {length_desc}",
        "value": len(password),
        "pass": length_weight >= 0.20,   # ≥ 8 chars = passing
    }

    # --- Character-class criteria ---
    for key, label, weight, test in _CHAR_CRITERIA:
        passed = test(password)
        if passed:
            score += weight
        details[key] = {"label": label, "pass": passed}

    score = round(min(1.0, score), 4)

    if score >= 0.67:
        strength = "strong"
    elif score >= 0.51:
        strength = "medium"
    elif score >= 0.34:
        strength = "weak"
    else:
        strength = "very_weak"

    return {
        "score": score,
        "strength": strength,
        "details": details,
        "recommendations": _build_recommendations(details),
    }


def _build_recommendations(details: dict) -> List[str]:
    """Build a list of actionable hints from the per-criterion detail dict."""
    recs: List[str] = []

    length_info = details.get("length", {})
    n = length_info.get("value", 0)
    if n < 8:
        recs.append("Use at least 8 characters (12+ strongly recommended)")
    elif n < 12:
        recs.append("Consider using 12+ characters for stronger security")

    char_hints = (
        ("has_uppercase", "Add uppercase letters (A–Z)"),
        ("has_lowercase", "Add lowercase letters (a–z)"),
        ("has_digit",     "Add numbers (0–9)"),
        ("has_special",   "Add special characters (e.g. !@#$%^&*)"),
    )
    for key, msg in char_hints:
        if not details.get(key, {}).get("pass"):
            recs.append(msg)

    return recs


def _generic_recommendations() -> List[str]:
    """Return generic recommendations when no password is provided."""
    return [
        "Use at least 12 characters",
        "Mix uppercase and lowercase letters",
        "Add numbers (0–9)",
        "Add special characters (e.g. !@#$%^&*)",
    ]


def get_strength_label(score: float) -> str:
    """
    Return a human-readable label for a normalized score in [0, 1].

    Args:
        score: float in [0.0, 1.0] from calculate_password_strength()

    Returns:
        str: one of 'Very Weak', 'Weak', 'Medium', 'Strong'
    """
    if score >= 0.67:
        return "Strong"
    if score >= 0.51:
        return "Medium"
    if score >= 0.34:
        return "Weak"
    return "Very Weak"


def get_strength_recommendations(password: str = None) -> List[str]:
    """
    Return actionable recommendations for improving password strength.

    Args:
        password: If provided, returns context-aware hints based on evaluated criteria.
                  If omitted, returns a generic list of best practices.

    Returns:
        list[str]: improvement suggestions
    """
    if password is not None:
        return calculate_password_strength(password)["recommendations"]
    return _generic_recommendations()
