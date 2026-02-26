"""
Utils package — shared utility functions.

Exports
-------
Keystroke processing:
  - process_web_events       — parse JS events → feature dict
  - assess_sample_quality    — score a feature dict for quality
  - compute_vector_stats     — descriptive stats for a timing vector

Password strength:
  - calculate_password_strength  — multi-criteria scoring (score 0.0–1.0)
  - get_strength_label           — human-readable label from score float
  - get_strength_recommendations — actionable hints (contextual or generic)
"""

from .keystroke_processor import (
    assess_sample_quality,
    compute_vector_stats,
    process_web_events,
)
from .password_strength import (
    calculate_password_strength,
    get_strength_label,
    get_strength_recommendations,
)

__all__ = [
    # keystroke
    "process_web_events",
    "assess_sample_quality",
    "compute_vector_stats",
    # password
    "calculate_password_strength",
    "get_strength_label",
    "get_strength_recommendations",
]
