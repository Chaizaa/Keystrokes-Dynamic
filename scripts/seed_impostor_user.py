"""
Seed a local impostor user for ML testing.

Creates a 'test_user2' account + 10 synthetic enrollment samples so that
the ML auto-train for any existing user (e.g. 'apis') has impostor data
and can satisfy the one-vs-rest minimum (genuine >= 2, impostor >= 2).

Usage:
    python scripts/seed_impostor_user.py [--username test_user2] [--samples 10]

Run from the project root (where config.py lives).
"""

import argparse
import json
import random
import sys
from datetime import datetime, timezone

# Allow running from repo root
sys.path.insert(0, ".")

from app import create_app
from app.models import db
from app.models.user import User
from app.models.keystroke_vector import UsersVector
from werkzeug.security import generate_password_hash


def _rand_vector(n: int, base_mean: float, jitter: float = 0.15) -> list[float]:
    """Produce n random timing values centred on base_mean (seconds)."""
    return [max(0.01, base_mean + random.gauss(0, base_mean * jitter)) for _ in range(n)]


def _stats(vals: list[float]) -> dict:
    mean = sum(vals) / len(vals)
    variance = sum((v - mean) ** 2 for v in vals) / len(vals)
    std = variance ** 0.5
    cv = (std / mean) if mean else 0.0
    return {"mean": mean, "std": std, "min": min(vals), "max": max(vals), "cv": cv}


def _make_sample(user_id: int, username: str) -> UsersVector:
    """Generate one synthetic enrollment row with random-but-realistic timings."""
    n = random.randint(6, 10)  # password key count

    # Slightly different base timings than typical genuine user → good impostor separation
    H  = _rand_vector(n, random.uniform(0.09, 0.18))
    DD = _rand_vector(n - 1, random.uniform(0.11, 0.22))
    UD = _rand_vector(n - 1, random.uniform(0.05, 0.15))
    UU = _rand_vector(n - 1, random.uniform(0.10, 0.21))
    DU = _rand_vector(n, random.uniform(0.08, 0.17))

    h_s  = _stats(H)
    dd_s = _stats(DD)
    ud_s = _stats(UD)
    uu_s = _stats(UU)
    du_s = _stats(DU)

    total_dur = sum(H) + sum(DD)
    typing_speed = n / total_dur if total_dur else 0.0

    return UsersVector(
        user_id=user_id,
        username=username,
        event_type="enrollment",
        data_type="enrollment",
        is_successful=True,
        timestamp=datetime.now(timezone.utc).isoformat(),
        # Vectors (JSON)
        H_vector=json.dumps(H),
        DD_vector=json.dumps(DD),
        UD_vector=json.dumps(UD),
        UU_vector=json.dumps(UU),
        DU_vector=json.dumps(DU),
        # Stats
        H_mean=h_s["mean"],   H_std=h_s["std"],   H_min=h_s["min"],   H_max=h_s["max"],   H_cv=h_s["cv"],
        DD_mean=dd_s["mean"],  DD_std=dd_s["std"],  DD_min=dd_s["min"],  DD_max=dd_s["max"],  DD_cv=dd_s["cv"],
        UD_mean=ud_s["mean"],  UD_std=ud_s["std"],  UD_min=ud_s["min"],  UD_max=ud_s["max"],  UD_cv=ud_s["cv"],
        UU_mean=uu_s["mean"],  UU_std=uu_s["std"],  UU_min=uu_s["min"],  UU_max=uu_s["max"],  UU_cv=uu_s["cv"],
        DU_mean=du_s["mean"],  DU_std=du_s["std"],  DU_min=du_s["min"],  DU_max=du_s["max"],  DU_cv=du_s["cv"],
        total_duration=total_dur,
        typing_speed=typing_speed,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", default="test_user2", help="Impostor username to create")
    parser.add_argument("--samples", type=int, default=10, help="Number of enrollment samples")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        # Create user if not exists
        existing = db.session.query(User).filter_by(username=args.username).one_or_none()
        if existing:
            user = existing
            print(f"[seed] User '{args.username}' already exists (id={user.id}), reusing.")
        else:
            user = User(
                username=args.username,
                password_hash=generate_password_hash("TestPass123!"),
                role="user",
                email_verified=True,
            )
            db.session.add(user)
            db.session.flush()  # get user.id before commit
            print(f"[seed] Created user '{args.username}' (id={user.id}).")

        # Check how many enrollment samples already exist
        existing_count = (
            db.session.query(UsersVector)
            .filter_by(username=args.username, event_type="enrollment")
            .count()
        )
        need = max(0, args.samples - existing_count)
        if need == 0:
            print(f"[seed] Already have {existing_count} enrollment samples — nothing to add.")
        else:
            for _ in range(need):
                db.session.add(_make_sample(user.id, args.username))
            print(f"[seed] Inserted {need} synthetic enrollment samples for '{args.username}'.")

        db.session.commit()
        print("[seed] Done. You can now trigger ML training for any other user.")
        print("       e.g.: python -c \"from app import create_app; from app.services.biometric_service import BiometricService; app=create_app(); ctx=app.app_context(); ctx.push(); print(BiometricService().train_user_model('apis', force=True))\"")


if __name__ == "__main__":
    main()
