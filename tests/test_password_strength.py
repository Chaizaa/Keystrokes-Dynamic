"""
Test: Password Strength Calculator
"""

import pytest

from app.utils.password_strength import (
    calculate_password_strength,
    get_strength_label,
    get_strength_recommendations,
)


# Test cases: (password, expected_strength_level)
test_passwords = [
    ("admin123", "Weak"),
    ("Password123", "Medium"),
    ("MyP@ssw0rd", "Strong"),  # Has uppercase, special char, digits
    ("MySecureP@ssw0rd2024", "Strong"),
    ("Str0ng!P@ssword#2024", "Strong"),
    ("abc", "Very Weak"),
]


@pytest.mark.parametrize("password,expected_level", test_passwords)
def test_password_strength_calculation(password, expected_level):
    """Test password strength calculation returns expected level."""
    result = calculate_password_strength(password)

    assert isinstance(result, dict), "Result should be a dict"
    assert "score" in result, "Result should have 'score'"
    assert "strength" in result, "Result should have 'strength'"
    assert 0.0 <= result["score"] <= 1.0, "Score should be between 0.0 and 1.0"

    # Test that get_strength_label correctly interprets the score
    label = get_strength_label(result["score"])
    assert expected_level in label, f"Expected '{expected_level}' in label '{label}' for password '{password}'"


def test_password_strength_weak_password_has_recommendations():
    """Test that weak passwords get recommendations."""
    weak_password = "abc"
    result = calculate_password_strength(weak_password)
    assert result["score"] < 0.34, "Test password should be weak"

    # Get recommendations for the password
    recommendations = get_strength_recommendations(weak_password)
    assert recommendations is not None, "Weak password should have recommendations"
    assert len(recommendations) > 0, "Weak password should have at least one recommendation"


def test_password_strength_recommendations_generic():
    """Test generic recommendations when no password provided."""
    recommendations = get_strength_recommendations(None)
    assert recommendations is not None, "Generic recommendations should exist"
    assert len(recommendations) > 0, "Should have at least one generic recommendation"
    assert isinstance(recommendations, list), "Recommendations should be a list"


def test_password_strength_includes_details():
    """Test that strength calculation includes detailed criteria."""
    password = "TestPass123!"
    result = calculate_password_strength(password)

    assert "details" in result, "Result should include detailed criteria"
    assert isinstance(result["details"], dict), "Details should be a dict"
    # Should have at least some criteria evaluated
    assert len(result["details"]) > 0, "Should have evaluated criteria"
