import sqlite3
import pickle
import numpy as np

from sklearn.ensemble import RandomForestClassifier

from app.ml.feature_builder import build_feature_matrix
from app.ml.thresholds import LOW_CONFIDENCE_THRESHOLD


def load_samples_from_db(db_path: str):

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    cursor = conn.execute("""
        SELECT username,
               H_vector,
               DD_vector,
               UD_vector,
               UU_vector,
               DU_vector
        FROM users_vectors
        WHERE event_type = 'enrollment'
    """)

    rows = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return rows


def prepare_labels(rows, target_user):

    X = build_feature_matrix(rows)

    y = np.array([
        1 if r["username"] == target_user else 0
        for r in rows
    ])

    return X, y


def train_model_from_db(db_path, target_user):

    rows = load_samples_from_db(db_path)

    X, y = prepare_labels(rows, target_user)

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=12,
        min_samples_leaf=5,
        class_weight="balanced",
        n_jobs=-1,
    )

    model.fit(X, y)

    bundle = {
        "model": model,
        "feature_dim": X.shape[1],
        "target_user": target_user,
        "threshold": LOW_CONFIDENCE_THRESHOLD,
    }

    return bundle


def save_model_to_db(db_path, target_user, bundle):

    blob = pickle.dumps(bundle)

    conn = sqlite3.connect(db_path)

    conn.execute("""
        INSERT OR REPLACE INTO ml_models
        (username, model_blob)
        VALUES (?, ?)
    """, (target_user, blob))

    conn.commit()
    conn.close()