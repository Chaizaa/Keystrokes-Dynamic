"""
Test: MLModelService model validation
======================================

Validates the new security checks in _deserialize_model()
"""

import io
import joblib
import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier

from app.services.ml_model_service import ml_model_service, FEATURE_COLUMNS


def test_deserialize_valid_model():
    """Test that a valid RandomForest model deserializes successfully."""
    # Create a minimal valid RandomForest model
    X_dummy = np.random.rand(10, len(FEATURE_COLUMNS))
    y_dummy = np.array([0, 1] * 5)

    model = RandomForestClassifier(n_estimators=5, random_state=42)
    model.fit(X_dummy, y_dummy)

    # Serialize it
    blob = ml_model_service._serialize_model(model)
    assert isinstance(blob, bytes), "Serialized model should be bytes"
    assert len(blob) > 0, "Serialized model should not be empty"

    # Deserialize it - should succeed
    deserialized = ml_model_service._deserialize_model(blob)
    assert isinstance(deserialized, RandomForestClassifier), "Should deserialize as RandomForest"
    assert deserialized.n_features_in_ == len(FEATURE_COLUMNS), "Feature count should match"


def test_deserialize_empty_blob():
    """Test that empty blob raises ValueError."""
    with pytest.raises(ValueError, match="empty or invalid"):
        ml_model_service._deserialize_model(b"")


def test_deserialize_invalid_blob():
    """Test that corrupted blob raises ValueError."""
    corrupted_blob = b"this is not a valid joblib pickle"
    with pytest.raises(ValueError, match="Failed to deserialize"):
        ml_model_service._deserialize_model(corrupted_blob)


def test_deserialize_wrong_model_type():
    """Test that non-RandomForest model raises ValueError."""
    from sklearn.svm import SVC

    # Create a SVM model (not RandomForest)
    X_dummy = np.random.rand(10, len(FEATURE_COLUMNS))
    y_dummy = np.array([0, 1] * 5)

    svm_model = SVC(probability=True)
    svm_model.fit(X_dummy, y_dummy)

    # Use joblib to serialize the SVM model
    buf = io.BytesIO()
    joblib.dump(svm_model, buf)
    blob = buf.getvalue()

    with pytest.raises(ValueError, match="must be RandomForestClassifier"):
        ml_model_service._deserialize_model(blob)


def test_deserialize_wrong_feature_count():
    """Test that model with wrong feature count raises ValueError."""
    # Create RandomForest with wrong number of features
    X_wrong = np.random.rand(10, 30)  # 30 features instead of 27
    y_dummy = np.array([0, 1] * 5)

    model = RandomForestClassifier(n_estimators=5, random_state=42)
    model.fit(X_wrong, y_dummy)

    # Use joblib to serialize the model
    buf = io.BytesIO()
    joblib.dump(model, buf)
    blob = buf.getvalue()

    with pytest.raises(ValueError, match="Feature count mismatch.*expected 27.*got 30"):
        ml_model_service._deserialize_model(blob)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
