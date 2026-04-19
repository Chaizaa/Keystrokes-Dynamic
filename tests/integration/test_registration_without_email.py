from sqlalchemy import func, select

from app.models import User, UsersVector, db


def _get_enrollment_count(username: str) -> int:
    return int(
        db.session.execute(
            select(func.count())
            .select_from(UsersVector)
            .where(
                UsersVector.username == username,
                (UsersVector.event_type == "enrollment")
                | (UsersVector.data_type == "enrollment"),
            )
        ).scalar()
        or 0
    )


def test_enroll_without_email_allows_creation_and_login(client, db_session, monkeypatch):
    username = "noemail_user"
    test_password = "NoEmailPass123!"

    # Cleanup any existing records
    try:
        db.session.query(UsersVector).filter(UsersVector.username == username).delete()
        db.session.query(User).filter(User.username == username).delete()
        db.session.commit()
    except Exception:
        db.session.rollback()

    assert _get_enrollment_count(username) == 0

    # Mock processing and quality
    def fake_process(events, username_arg):
        return {
            "status": "success",
            "features": {"H_vector": [0.1, 0.2], "DD_vector": [0.05, 0.06]},
            "real_password_string": test_password,
            "password_hash": None,
        }

    monkeypatch.setattr("app.blueprints.api.process_web_events", fake_process)
    monkeypatch.setattr(
        "app.blueprints.api.assess_sample_quality",
        lambda f: {"quality_label": "good", "quality_score": 0.95},
    )

    payload = {
        "username": username,
        "events": [{"type": "keydown", "key": "a"}],
        "email": None,
    }

    # Enroll 20 samples
    for i in range(20):
        resp = client.post("/api/register_sample", json=payload)
        assert resp.status_code == 200, resp.get_json()
        j = resp.get_json()
        assert j.get("status") == "success"

    # Now the DB should report >=20 samples for this user
    count = _get_enrollment_count(username)
    assert count >= 20

    # Confirm user exists and has no email
    u = db.session.execute(select(User).where(User.username == username)).scalars().first()
    assert u is not None
    assert u.email in (None, "")

    # Spy on biometric verify to assert >=20 samples before login
    def spy_verify(username_arg, features_arg, *args, **kwargs):
        current = _get_enrollment_count(username)
        assert current >= 20
        return {"success": True, "verified": True, "score": 0.95, "confidence": "high"}

    monkeypatch.setattr("app.blueprints.api.biometric_service.verify_keystroke_sample", spy_verify)

    # Attempt login using keystrokes
    login_resp = client.post(
        "/api/login",
        json={"username": username, "events": [{"type": "keydown", "key": "a"}]},
    )
    assert login_resp.status_code == 200, login_resp.get_json()
    j = login_resp.get_json()
    assert j.get("success") is True
    assert j.get("score", 0) >= 0.9
