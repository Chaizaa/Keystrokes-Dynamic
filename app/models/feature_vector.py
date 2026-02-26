"""
Compatibility stub — FeatureVector and EnrollmentVector have been merged into UsersVector.

All keystroke data is now stored in the users_vectors table via the UsersVector model.

DEPRECATED: This module will be removed in a future release.
Update all imports to use ``UsersVector`` from ``app.models.keystroke_vector`` directly.
"""

import warnings as _warnings

from .keystroke_vector import UsersVector


def _deprecated_alias(name: str):
    _warnings.warn(
        f"{name} is deprecated and will be removed in a future release. "
        "Use UsersVector from app.models.keystroke_vector instead.",
        DeprecationWarning,
        stacklevel=3,
    )
    return UsersVector


# Backward-compatibility aliases — preserved so existing imports keep working.
FeatureVector    = UsersVector
EnrollmentVector = UsersVector

__all__ = ["FeatureVector", "EnrollmentVector"]
