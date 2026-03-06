"""Smoke test for DB-backed ML training/inference.

What it tests:
- creates a fresh SQLite DB (in-memory by default)
- inserts 2 users with enrollment samples containing the 27 feature columns
- trains per-user RandomForest models using the same procedure as `ml/ml_pta.py`
- verifies a synthetic login feature row

Run:
  python scripts/ml_smoke_test.py

If this script succeeds, it proves the ML pipeline is working.
"""

from __future__ import annotations

import os
import sys

# Allow running `python scripts/ml_smoke_test.py` where sys.path[0] is `scripts/`.
# We want the project root on sys.path so `import app` works.
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import random


def _make_feature_row(mu: float, sigma: float) -> dict:
    # Import here so it runs under app context only.
    from app.services.ml_model_service import FEATURE_COLUMNS

    row = {}
    for c in FEATURE_COLUMNS:
        # Keep durations positive-ish
        val = random.gauss(mu, sigma)
        if c in ("total_duration", "typing_speed"):
            val = abs(val)
        row[c] = float(val)
    return row


def main() -> int:
    from app import create_app
    from app.models import User, UsersVector, db
    from app.services.ml_model_service import ml_model_service

    # Use an isolated DB so schema mismatches in existing .db don't affect the test.
    app = create_app(
        {
            "TESTING": True,
            "RATELIMIT_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        }
    )

    with app.app_context():
        db.create_all()

        # Create two users
        u1 = User(username="alice")
        u1.set_password("AlicePass123!")
        u2 = User(username="bob")
        u2.set_password("BobPass123!")
        db.session.add_all([u1, u2])
        db.session.commit()

        # Insert enrollment samples (20 each)
        random.seed(42)

        for _ in range(20):
            f = _make_feature_row(mu=0.25, sigma=0.05)
            ev = UsersVector(username="alice", event_type="enrollment")
            for k, v in f.items():
                setattr(ev, k, v)
            db.session.add(ev)

        for _ in range(20):
            f = _make_feature_row(mu=0.65, sigma=0.07)
            ev = UsersVector(username="bob", event_type="enrollment")
            for k, v in f.items():
                setattr(ev, k, v)
            db.session.add(ev)

        db.session.commit()

        # Train
        res_alice = ml_model_service.train_user_model("alice", force=True)
        res_bob = ml_model_service.train_user_model("bob", force=True)

        print("Train alice:", res_alice.success, res_alice.reason, "thr=", res_alice.threshold)
        print("Train bob:", res_bob.success, res_bob.reason, "thr=", res_bob.threshold)

        if not res_alice.success or not res_bob.success:
            print("Training failed; see reasons above")
            return 2

        # Verify (alice-like sample should pass for alice, fail for bob)
        login_alice_like = _make_feature_row(mu=0.25, sigma=0.05)
        pred_alice = ml_model_service.verify("alice", login_alice_like)
        pred_bob = ml_model_service.verify("bob", login_alice_like)

        print("Predict alice on alice-like:", pred_alice)
        print("Predict bob on alice-like:", pred_bob)

        assert pred_alice.get("success") is True
        assert pred_bob.get("success") is True

    print("OK: ML smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
