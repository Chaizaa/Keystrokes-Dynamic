import pytest
from sqlalchemy import func, select

from app.models import EnrollmentVector, User, db


def test_register_sample_persists_for_existing_user(client, db_session, monkeypatch):
    """Existing user with 0 samples should be able to save a first sample and it should persist."""
    # Create an existing user with no enrollment samples
    user = User(username="persistuser")
    user.set_password("TestPass123!")
    db.session.add(user)
    db.session.commit()

    initial_count = db.session.execute(
        select(func.count())
        .select_from(EnrollmentVector)
        .where(
            EnrollmentVector.username == "persistuser",
            EnrollmentVector.event_type == "enrollment",
        )
    ).scalar_one()
    assert int(initial_count) == 0

    # Mock processing to return a valid features object and password string
    def fake_process(events, username):
        return {
            "status": "success",
            "features": {"H_vector": [0.1, 0.2], "DD_vector": [0.05, 0.06]},
            "real_password_string": "TestPass123!",
            "password_hash": None,
        }

    monkeypatch.setattr("app.blueprints.api.process_web_events", fake_process)
    monkeypatch.setattr(
        "app.blueprints.api.assess_sample_quality",
        lambda f: {"quality_label": "good", "quality_score": 0.9},
    )

    payload = {"username": "persistuser", "events": [{"type": "keydown", "key": "a"}]}

    resp = client.post("/api/register_sample", json=payload)
    assert resp.status_code == 200, resp.get_json()
    j = resp.get_json()
    assert j.get("status") == "success"

    enrollment_count = db.session.execute(
        select(func.count())
        .select_from(EnrollmentVector)
        .where(
            EnrollmentVector.username == "persistuser",
            EnrollmentVector.event_type == "enrollment",
        )
    ).scalar_one()
    assert int(enrollment_count) == 1
