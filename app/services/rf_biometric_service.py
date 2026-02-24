# app/services/rf_biometric_service.py
from typing import Dict, Any
import joblib
import numpy as np

from app.ml.feature_builder import build_feature_vector


class RFBiometricService:
    def __init__(self, model_path: str):
        self.bundle = joblib.load(model_path)
        self.model = self.bundle["model"]
        self.threshold = float(self.bundle.get("threshold", 0.7))
        self.feature_dim = int(self.bundle.get("feature_dim", 35))
        self.target_user = self.bundle.get("target_user")

    def verify_sample(self, sample: Dict[str, Any], username: str) -> Dict[str, Any]:
        if self.target_user and username != self.target_user:
            return {
                "verified": False,
                "score": 0.0,
                "reason": "username_model_mismatch",
                "model": "random_forest",
            }

        x = np.array([build_feature_vector(sample)], dtype=float)
        if x.shape[1] != self.feature_dim:
            return {
                "verified": False,
                "score": 0.0,
                "reason": "feature_dim_mismatch",
                "model": "random_forest",
            }

        prob_genuine = float(self.model.predict_proba(x)[0, 1])
        verified = prob_genuine >= self.threshold

        return {
            "verified": bool(verified),
            "score": prob_genuine,
            "threshold": self.threshold,
            "model": "random_forest",
        }
