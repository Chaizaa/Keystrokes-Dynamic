"""BiometricService - Keystroke dynamics biometric analysis and verification."""

from typing import Dict, List

import os
import sqlite3
from config import basedir, Config

import numpy as np


class BiometricService:
    """Service class for biometric keystroke analysis and verification."""

    def __init__(self, db=None):
        self.db = db
        self.EXACT_MATCH_THRESHOLD = 0.95
        self.HIGH_CONFIDENCE_THRESHOLD = 0.85
        self.MEDIUM_CONFIDENCE_THRESHOLD = 0.70
        self.LOW_CONFIDENCE_THRESHOLD = 0.55
        self.MIN_SAMPLES_FOR_VERIFICATION = 3
        self.RECOMMENDED_SAMPLES = 10

    def calculate_euclidean_distance(self, vec1: List[float], vec2: List[float]) -> float:
        if len(vec1) != len(vec2):
            raise ValueError("Vectors must have same length")
        v1 = np.array(vec1, dtype=float)
        v2 = np.array(vec2, dtype=float)
        return float(np.linalg.norm(v1 - v2))

    def calculate_cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        if len(vec1) != len(vec2):
            raise ValueError("Vectors must have same length")
        v1 = np.array(vec1, dtype=float)
        v2 = np.array(vec2, dtype=float)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(v1, v2) / (norm1 * norm2))

    def calculate_statistical_similarity(self, sample: Dict, enrollment_list: List[Dict]) -> Dict:
        import statistics

        if not enrollment_list:
            return {
                "score": 0.0,
                "mean_h_diff": float("nan"),
                "std_h_diff": float("nan"),
            }
        try:
            sample_h = [float(x) for x in sample.get("H_vector", [])]
        except Exception:
            return {
                "score": 0.0,
                "mean_h_diff": float("nan"),
                "std_h_diff": float("nan"),
            }
        template_rows = []
        for t in enrollment_list:
            hv = t.get("H_vector") or []
            try:
                template_rows.append([float(x) for x in hv])
            except Exception:
                continue
        if not sample_h or not template_rows:
            return {
                "score": 0.0,
                "mean_h_diff": float("nan"),
                "std_h_diff": float("nan"),
            }
        min_len = min(len(sample_h), min(len(r) for r in template_rows))
        if min_len == 0:
            return {
                "score": 0.0,
                "mean_h_diff": float("nan"),
                "std_h_diff": float("nan"),
            }
        sample_h = sample_h[:min_len]
        trimmed = [[r[i] for i in range(min_len)] for r in template_rows]
        template_means = [statistics.mean(col) for col in zip(*trimmed)]
        diffs = [abs(a - b) for a, b in zip(sample_h, template_means)]
        mean_h_diff = statistics.mean(diffs)
        std_h_diff = statistics.pstdev(diffs) if len(diffs) > 1 else 0.0
        # Scale mean diff to make score more discriminative for large diffs
        score = 1.0 / (1.0 + (mean_h_diff * 2.0))
        return {
            "score": float(score),
            "mean_h_diff": float(mean_h_diff),
            "std_h_diff": float(std_h_diff),
        }

    def get_enrollment_status(self, username: str) -> Dict:
        """Return enrollment status for a username.

        Returns a dict with:
          - count: number of enrollment samples
          - enrolled: boolean (>= MIN_SAMPLES_FOR_VERIFICATION)
          - ready_for_login: boolean (>= RECOMMENDED_SAMPLES)
          - minimum_samples: MIN_SAMPLES_FOR_VERIFICATION
          - recommended_samples: RECOMMENDED_SAMPLES

        Implementation uses a single ORM query on ``UsersVector`` (the canonical
        enrollment table keyed by ``data_type = 'enrollment'``) with one raw-SQL
        fallback for legacy ``enrollment_vectors`` rows that may exist in older DBs.
        """
        count = 0

        # ── Primary path: single ORM query on UsersVector ───────────────────
        try:
            from sqlalchemy import func, select

            from app.models import UsersVector
            from app.models import db as sqlalchemy_db

            stmt = (
                select(func.count())
                .select_from(UsersVector)
                .where(
                    UsersVector.username == username,
                    UsersVector.event_type == "enrollment",
                )
            )
            count = int(sqlalchemy_db.session.execute(stmt).scalar_one())
            print(f"[DB] Enrollment count from UsersVector: {count}")
        except Exception as primary_err:
            print(f"[DB] ORM enrollment count failed ({primary_err}), using legacy fallback")

            # ── Fallback: legacy enrollment_vectors / user_vectors tables ────
            try:
                db_path = os.path.join(basedir, Config.DATABASE_PATH)
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                try:
                    cursor.execute(
                        "SELECT COUNT(*) FROM enrollment_vectors WHERE username = ?",
                        (username,),
                    )
                    count = cursor.fetchone()[0] or 0
                except sqlite3.OperationalError:
                    try:
                        cursor.execute(
                            "SELECT COUNT(*) FROM user_vectors WHERE username = ? "
                            "AND (event_type = 'enrollment' OR event_type = 'enrollment')",
                            (username,),
                        )
                        count = cursor.fetchone()[0] or 0
                    except Exception:
                        count = 0
                conn.close()
            except Exception as fallback_err:
                print(f"[DB ERROR] Enrollment fallback failed: {fallback_err}")
                count = 0

        enrolled = count >= self.MIN_SAMPLES_FOR_VERIFICATION
        ready_for_login = count >= self.RECOMMENDED_SAMPLES

        return {
            "count": int(count),
            "enrolled": bool(enrolled),
            "ready_for_login": bool(ready_for_login),
            "minimum_samples": self.MIN_SAMPLES_FOR_VERIFICATION,
            "recommended_samples": self.RECOMMENDED_SAMPLES,
        }

    def verify_keystroke_sample(self, arg1, arg2=None, use_statistical: bool = True) -> Dict:
        """Verify a keystroke sample against templates.

        Supports two call styles:
        - (username: str, login_sample: dict)
        - (login_sample: dict, enrollment_list: list)
        """
        if isinstance(arg1, str):
            username = arg1
            login_sample = arg2
            templates = self.db.get_enrollment_samples(username) if self.db else []
            legacy = True
        else:
            login_sample = arg1
            templates = arg2 or []
            legacy = False

        # Validate templates
        if not templates or len(templates) < self.MIN_SAMPLES_FOR_VERIFICATION:
            return (
                {"error": "insufficient enrollment samples", "decision": "impostor"}
                if not legacy
                else {
                    "success": False,
                    "verified": False,
                    "score": 0.0,
                    "reason": "insufficient_samples",
                    "message": f"Need at least {self.MIN_SAMPLES_FOR_VERIFICATION} enrollment samples",
                }
            )

        # Validate vectors
        login_H = login_sample.get("H_vector", [])
        login_DD = login_sample.get("DD_vector", [])
        if not login_H or not login_DD:
            return (
                {"error": "missing required vectors", "decision": "impostor"}
                if not legacy
                else {
                    "success": False,
                    "verified": False,
                    "score": 0.0,
                    "reason": "invalid_features",
                    "message": "Missing required keystroke features",
                }
            )

        eu_scores = []
        cos_scores = []
        stat_scores = []

        for t in templates:
            tH = t.get("H_vector", [])
            tDD = t.get("DD_vector", [])
            if len(tH) != len(login_H) or len(tDD) != len(login_DD):
                continue

            h_dist = self.calculate_euclidean_distance(login_H, tH)
            dd_dist = self.calculate_euclidean_distance(login_DD, tDD)
            eu = (1.0 / (1.0 + h_dist) + 1.0 / (1.0 + dd_dist)) / 2
            eu_scores.append(eu)

            h_cos = self.calculate_cosine_similarity(login_H, tH)
            dd_cos = self.calculate_cosine_similarity(login_DD, tDD)
            cos = (((h_cos + 1) / 2) + ((dd_cos + 1) / 2)) / 2
            cos_scores.append(cos)

            s = self.calculate_statistical_similarity(login_sample, templates)
            stat_scores.append(s.get("score", 0.0))

        if not eu_scores and not cos_scores and not stat_scores:
            return (
                {
                    "error": "no valid template comparisons (length mismatch)",
                    "decision": "impostor",
                }
                if not legacy
                else {
                    "success": False,
                    "verified": False,
                    "score": 0.0,
                    "reason": "password_length_mismatch",
                    "message": "Password length does not match enrollment. Please type the same password you registered with",
                }
            )

        eu_score = float(np.mean(eu_scores)) if eu_scores else 0.0
        cos_score = float(np.mean(cos_scores)) if cos_scores else 0.0
        statistical_score = float(np.mean(stat_scores)) if stat_scores else 0.0

        # Base weighted confidence
        base_confidence = 0.5 * eu_score + 0.3 * cos_score + 0.2 * statistical_score
        base_confidence = float(max(0.0, min(1.0, base_confidence)))

        # Calibrate confidence by emphasizing statistical alignment (reduces false positives)
        calibrated_confidence = float(max(0.0, min(1.0, base_confidence * statistical_score)))

        if legacy:
            verified = calibrated_confidence >= self.LOW_CONFIDENCE_THRESHOLD
            confidence_label = (
                "exact_match"
                if calibrated_confidence >= self.EXACT_MATCH_THRESHOLD
                else (
                    "high"
                    if calibrated_confidence >= self.HIGH_CONFIDENCE_THRESHOLD
                    else (
                        "medium"
                        if calibrated_confidence >= self.MEDIUM_CONFIDENCE_THRESHOLD
                        else (
                            "low"
                            if calibrated_confidence >= self.LOW_CONFIDENCE_THRESHOLD
                            else "failed"
                        )
                    )
                )
            )
            return {
                "success": True,
                "verified": verified,
                "score": float(round(calibrated_confidence, 4)),
                "avg_score": float(round(np.mean([eu_score, cos_score, statistical_score]), 4)),
                "confidence": confidence_label,
                "templates_used": len(templates),
                "message": (
                    "Biometric verification successful"
                    if verified
                    else "Biometric verification failed"
                ),
            }

        confidence_score = calibrated_confidence
        decision = "genuine" if confidence_score >= self.MEDIUM_CONFIDENCE_THRESHOLD else "impostor"
        if confidence_score >= self.EXACT_MATCH_THRESHOLD:
            label = "Exact Match"
        elif confidence_score >= self.HIGH_CONFIDENCE_THRESHOLD:
            label = "High Confidence"
        elif confidence_score >= self.MEDIUM_CONFIDENCE_THRESHOLD:
            label = "Medium Confidence"
        elif confidence_score >= self.LOW_CONFIDENCE_THRESHOLD:
            label = "Low Confidence"
        else:
            label = "Very Low Confidence"

        primary_metric = (
            "euclidean"
            if eu_score >= max(cos_score, statistical_score)
            else ("cosine" if cos_score >= statistical_score else "statistical")
        )

        return {
            "decision": decision,
            "confidence_score": float(round(confidence_score, 4)),
            "confidence_label": label,
            "euclidean_score": float(round(eu_score, 4)),
            "cosine_score": float(round(cos_score, 4)),
            "statistical_score": float(round(statistical_score, 4)),
            "primary_metric": primary_metric,
        }
