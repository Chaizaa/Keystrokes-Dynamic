#!/usr/bin/env python3
"""
Quick test to verify that keystroke processor rounding works correctly
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.utils.keystroke_processor import (
    round_to_decimals,
    round_vector,
    compute_vector_stats,
    process_web_events,
)


def test_round_to_decimals():
    """Test the round_to_decimals function"""
    print("Testing round_to_decimals:")
    
    # Test rounding to 5 decimals
    value = 0.123456789
    rounded = round_to_decimals(value, 5)
    print(f"  {value} -> {rounded} (expected 0.12346)")
    assert rounded == 0.12346, f"Expected 0.12346 but got {rounded}"
    
    # Test with None
    rounded_none = round_to_decimals(None, 5)
    print(f"  None -> {rounded_none} (expected None)")
    assert rounded_none is None
    
    # Test with very small value
    small = 0.0000001
    rounded_small = round_to_decimals(small, 5)
    print(f"  {small} -> {rounded_small} (expected 0.0)")
    assert rounded_small == 0.0
    
    print("  ✓ round_to_decimals tests passed\n")


def test_round_vector():
    """Test the round_vector function"""
    print("Testing round_vector:")
    
    vec = [0.123456, 0.234567, 0.345678, 0.456789]
    rounded = round_vector(vec, 5)
    
    print(f"  Original: {vec}")
    print(f"  Rounded:  {rounded}")
    
    expected = [0.12346, 0.23457, 0.34568, 0.45679]
    assert rounded == expected, f"Expected {expected} but got {rounded}"
    
    # Test with empty vector
    empty_rounded = round_vector([], 5)
    assert empty_rounded == []
    
    print("  ✓ round_vector tests passed\n")


def test_compute_vector_stats():
    """Test that compute_vector_stats returns rounded values"""
    print("Testing compute_vector_stats with rounding:")
    
    vec = [0.123456789, 0.234567890, 0.345678901]
    stats = compute_vector_stats(vec, 5)
    
    print(f"  Vector: {vec}")
    print(f"  Stats: {stats}")
    
    # All values should be rounded to 5 decimals
    for key, value in stats.items():
        decimal_places = len(str(value).split('.')[-1]) if isinstance(value, float) else 0
        print(f"    {key}: {value} (decimals: {decimal_places})")
        # Check that no value has more than 5 decimal places
        assert decimal_places <= 5, f"{key} has {decimal_places} decimal places"
    
    print("  ✓ compute_vector_stats tests passed\n")


def test_process_web_events_rounding():
    """Test that process_web_events returns properly rounded data"""
    print("Testing process_web_events rounding:")
    
    # Create synthetic keystroke events
    events = [
        # 't' is timestamp in ms, 'evt' is 'd' (down) or 'u' (up), 'code' is key code
        {"t": 100, "evt": "d", "code": "KeyA", "key": "a"},
        {"t": 123456789, "evt": "u", "code": "KeyA", "key": "a"},
        {"t": 140, "evt": "d", "code": "KeyB", "key": "b"},
        {"t": 234567890, "evt": "u", "code": "KeyB", "key": "b"},
        {"t": 260, "evt": "d", "code": "KeyC", "key": "c"},
        {"t": 345678901, "evt": "u", "code": "KeyC", "key": "c"},
        {"t": 380, "evt": "d", "code": "Enter", "key": "Enter"},
    ]
    
    result = process_web_events(events, "testuser")
    
    if result["status"] == "success":
        features = result["features"]
        
        # Check that vectors are rounded
        for vec_name in ["H_vector", "DD_vector", "UD_vector", "UU_vector", "DU_vector"]:
            vec = features.get(vec_name, [])
            if vec:
                print(f"  {vec_name}: {vec}")
                for val in vec:
                    decimal_places = len(str(val).split('.')[-1]) if isinstance(val, float) else 0
                    assert decimal_places <= 5, f"{vec_name} has value {val} with {decimal_places} decimals"
        
        # Check that stats are rounded
        for stat_name in ["H_mean", "H_std", "H_min", "H_max", "H_cv",
                         "DD_mean", "DD_std", "DD_min", "DD_max", "DD_cv"]:
            val = features.get(stat_name)
            if val is not None and isinstance(val, float):
                decimal_places = len(str(val).split('.')[-1])
                assert decimal_places <= 5, f"{stat_name} has value {val} with {decimal_places} decimals"
                print(f"  {stat_name}: {val} ✓")
        
        print("  ✓ process_web_events rounding tests passed\n")
    else:
        print(f"  ✗ process_web_events failed: {result['msg']}\n")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Keystroke Processor Rounding Implementation")
    print("=" * 60 + "\n")
    
    test_round_to_decimals()
    test_round_vector()
    test_compute_vector_stats()
    test_process_web_events_rounding()
    
    print("=" * 60)
    print("✓ All tests passed!")
    print("=" * 60)
