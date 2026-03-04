"""
ML-only Biometric Service
Fully Machine Learning based keystroke verification using Random Forest.
No statistical fallback.
Uses database as source of truth.
"""

from typing import Dict, Any, Optional
import sqlite3
import pickle
import numpy as np

from app.ml.feature_builder import build_feature_vector, build_feature_matrix
from app.ml.thresholds import (
    EXACT_MATCH_THRESHOLD,
    HIGH_CONFIDENCE_THRESHOLD,
    MEDIUM_CONFIDENCE_THRESHOLD,
    LOW_CONFIDENCE_THRESHOLD,
    MIN_SAMPLES_FOR_VERIFICATION,
    RECOMMENDED_SAMPLES,
    get_confidence_label,
)

from sklearn.ensemble import RandomForestClassifier


class MLBiometricService:

    def __init__(self, db_path: str):
        self.db_path = db_path

    # ============================================================
    # DATABASE FUNCTIONS
    # ============================================================

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def get_enrollment_count(self, username: str) -> int:

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*)
            FROM users_vectors
            WHERE username = ?
            AND event_type = 'enrollment'
        """, (username,))

        count = cursor.fetchone()[0]

        conn.close()

        return int(count)

    def get_enrollment_samples(self, username: str):

        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT username,
                   H_vector,
                   DD_vector,
                   UD_vector,
                   UU_vector,
                   DU_vector
            FROM users_vectors
            WHERE username = ?
            AND event_type = 'enrollment'
        """, (username,))

        rows = [dict(r) for r in cursor.fetchall()]

        conn.close()

        return rows

    # ============================================================
    # MODEL STORAGE
    # ============================================================

    def load_model(self, username: str):

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT model_blob
            FROM ml_models
            WHERE username = ?
        """, (username,))

        row = cursor.fetchone()

        conn.close()

        if row:
            return pickle.loads(row[0])

        return None

    def save_model(self, username: str, bundle: Dict[str, Any]):

        blob = pickle.dumps(bundle)

        conn = self._get_connection()

        conn.execute("""
            INSERT OR REPLACE INTO ml_models
            (username, model_blob)
            VALUES (?, ?)
        """, (username, blob))

        conn.commit()
        conn.close()

    # ============================================================
    # MODEL TRAINING
    # ============================================================

    def train_model(self, username: str) -> Dict[str, Any]:

        rows = self.get_enrollment_samples(username)

        if len(rows) < MIN_SAMPLES_FOR_VERIFICATION:

            return {
                "success": False,
                "reason": "insufficient_samples",
                "required": MIN_SAMPLES_FOR_VERIFICATION,
                "current": len(rows),
            }

        X = build_feature_matrix(rows)

        y = np.ones(len(rows))  # genuine samples

        # Add impostor samples (other users)
        impostor_rows = self._get_impostor_samples(username)

        if impostor_rows:

            X_imp = build_feature_matrix(impostor_rows)
            y_imp = np.zeros(len(impostor_rows))

            X = np.vstack([X, X_imp])
            y = np.concatenate([y, y_imp])

        model = RandomForestClassifier(

            n_estimators=300,
            max_depth=12,
            min_samples_leaf=5,
            class_weight="balanced",
            n_jobs=-1,
            random_state=42

        )

        model.fit(X, y)

        bundle = {

            "model": model,
            "feature_dim": X.shape[1],
            "threshold": LOW_CONFIDENCE_THRESHOLD,
            "username": username

        }

        self.save_model(username, bundle)

        return {
            "success": True,
            "samples_used": len(rows),
            "feature_dim": X.shape[1],
        }

    def _get_impostor_samples(self, username: str, limit: int = 200):

        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT username,
                   H_vector,
                   DD_vector,
                   UD_vector,
                   UU_vector,
                   DU_vector
            FROM users_vectors
            WHERE username != ?
            AND event_type = 'enrollment'
            LIMIT ?
        """, (username, limit))

        rows = [dict(r) for r in cursor.fetchall()]

        conn.close()

        return rows

    # ============================================================
    # VERIFICATION (ML ONLY)
    # ============================================================

    def verify(self, username: str, sample: Dict[str, Any]) -> Dict[str, Any]:

        # Check enrollment count
        count = self.get_enrollment_count(username)

        if count < MIN_SAMPLES_FOR_VERIFICATION:

            return {
                "verified": False,
                "reason": "insufficient_enrollment_samples",
                "current_samples": count,
                "required_samples": MIN_SAMPLES_FOR_VERIFICATION,
            }

        # Load model
        bundle = self.load_model(username)

        # Auto train if model missing
        if not bundle:

            train_result = self.train_model(username)

            if not train_result["success"]:

                return {
                    "verified": False,
                    "reason": "model_training_failed",
                    "details": train_result,
                }

            bundle = self.load_model(username)

        model = bundle["model"]
        feature_dim = bundle["feature_dim"]

        x = np.array([build_feature_vector(sample)], dtype=float)

        if x.shape[1] != feature_dim:

            return {
                "verified": False,
                "reason": "feature_dimension_mismatch",
                "expected": feature_dim,
                "received": x.shape[1],
            }

        prob = float(model.predict_proba(x)[0, 1])

        verified = prob >= LOW_CONFIDENCE_THRESHOLD

        return {

            "verified": verified,
            "score": prob,
            "confidence": get_confidence_label(prob),

            "thresholds": {
                "exact": EXACT_MATCH_THRESHOLD,
                "high": HIGH_CONFIDENCE_THRESHOLD,
                "medium": MEDIUM_CONFIDENCE_THRESHOLD,
                "low": LOW_CONFIDENCE_THRESHOLD,
            },

            "model": "random_forest",
            "samples_used": count,
        }

    # ============================================================
    # STATUS
    # ============================================================

    def get_status(self, username: str):

        count = self.get_enrollment_count(username)

        return {

            "enrollment_count": count,

            "enrolled": count >= MIN_SAMPLES_FOR_VERIFICATION,

            "ready": count >= RECOMMENDED_SAMPLES,

            "model_exists": self.load_model(username) is not None,

            "minimum_required": MIN_SAMPLES_FOR_VERIFICATION,

            "recommended": RECOMMENDED_SAMPLES,

        }