"""Integration tests for partner-facing API key endpoints."""

from app.models import APIKey, EnrollmentLog, User, VerificationLog, db
from app.services import APIKeyService


def _create_owner(username="partner_owner"):
    owner = User(username=username)
    owner.set_password("OwnerPass123!")
    db.session.add(owner)
    db.session.commit()
    return owner


def test_partner_endpoints_require_api_key(client, db_session):
    payload = {"username": "partner_user", "events": [{"evt": "d", "t": 1}]}

    enroll_resp = client.post("/api/partner/enroll", json=payload)
    assert enroll_resp.status_code == 401
    assert enroll_resp.get_json().get("error_code") == "INVALID_API_KEY"

    verify_resp = client.post("/api/partner/verify", json=payload)
    assert verify_resp.status_code == 401
    assert verify_resp.get_json().get("error_code") == "INVALID_API_KEY"


def test_partner_enroll_and_verify_flow(client, db_session, monkeypatch):
    owner = _create_owner("partner_owner_flow")
    full_key, key_model = APIKeyService.generate_new_key(
        user_id=owner.id,
        partner_name="Acme Integration",
    )

    def fake_process_web_events(events, username):
        return {
            "status": "success",
            "features": {
                "H_vector": [0.11, 0.12, 0.13],
                "DD_vector": [0.07, 0.08, 0.09],
                "UD_vector": [0.02, 0.03],
            },
            "real_password_string": "UserPass123!",
            "password_hash": "sha256_dummy_hash",
        }

    monkeypatch.setattr("app.blueprints.api.process_web_events", fake_process_web_events)
    monkeypatch.setattr(
        "app.blueprints.api.biometric_service.verify_keystroke_sample",
        lambda features, templates: {
            "decision": "genuine",
            "confidence_score": 0.93,
            "confidence_label": "High Confidence",
        },
    )

    headers = {"Authorization": f"Bearer {full_key}"}
    enroll_payload = {
        "username": "partner_flow_user",
        "events": [{"evt": "d", "code": "KeyA", "key": "a", "t": 1}],
    }

    for _ in range(3):
        enroll_resp = client.post("/api/partner/enroll", json=enroll_payload, headers=headers)
        assert enroll_resp.status_code == 201, enroll_resp.get_json()
        assert enroll_resp.get_json().get("success") is True

    verify_resp = client.post("/api/partner/verify", json=enroll_payload, headers=headers)
    assert verify_resp.status_code == 200, verify_resp.get_json()

    verify_data = verify_resp.get_json()
    assert verify_data.get("success") is True
    assert verify_data.get("verified") is True
    assert verify_data.get("decision") == "genuine"

    assert EnrollmentLog.query.filter_by(api_key_id=key_model.id).count() == 3
    assert VerificationLog.query.filter_by(api_key_id=key_model.id).count() == 1

    refreshed_key = db.session.get(APIKey, key_model.id)
    assert refreshed_key.total_enrollments == 3
    assert refreshed_key.total_verifications == 1
    assert refreshed_key.last_used_at is not None


def test_partner_enroll_blocks_disallowed_origin(client, db_session):
    owner = _create_owner("partner_owner_origin")
    full_key, _ = APIKeyService.generate_new_key(
        user_id=owner.id,
        partner_name="Origin Locked Partner",
        allowed_origins="trusted.example.com",
    )

    headers = {
        "Authorization": f"Bearer {full_key}",
        "Origin": "https://evil.example.com",
    }
    payload = {"username": "partner_user", "events": [{"evt": "d", "t": 1}]}

    response = client.post("/api/partner/enroll", json=payload, headers=headers)
    assert response.status_code == 403
    data = response.get_json()
    assert data.get("error_code") == "ORIGIN_NOT_ALLOWED"
