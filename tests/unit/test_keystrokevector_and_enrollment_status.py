"""
Tests for KeystrokeVector username auto-population and BiometricService enrollment status behavior
"""
import pytest


def test_keystrokevector_auto_populates_username(db_session, sample_user):
    """When only user_id is provided, KeystrokeVector should auto-fill username (best-effort)."""
    from app.models import KeystrokeVector

    kv = KeystrokeVector(
        user_id=sample_user.id,
        h_vector='[0.1, 0.2, 0.3]',
        dd_vector='[0.05, 0.06, 0.07]',
        ud_vector='[0.15, 0.16, 0.17]',
        data_type='enrollment'
    )
    db_session.add(kv)
    db_session.commit()

    # Use provided db_session to fetch the object (avoids deprecated Query.get)
    fetched = db_session.get(KeystrokeVector, kv.id)
    assert fetched is not None
    assert fetched.username == sample_user.username


def test_get_enrollment_status_counts_with_userid_only_samples(biometric_service, db_session, sample_user):
    """Ensure enrollment status counts samples created with only user_id (no username) correctly."""
    from app.models import KeystrokeVector

    # Create 3 enrollment samples using only user_id (no username)
    for i in range(3):
        kv = KeystrokeVector(
            user_id=sample_user.id,
            h_vector=f"[0.{i}, 0.2, 0.3]",
            dd_vector='[0.05, 0.06, 0.07]',
            ud_vector='[0.15, 0.16, 0.17]',
            data_type='enrollment'
        )
        db_session.add(kv)
    db_session.commit()

    status = biometric_service.get_enrollment_status(sample_user.username)

    assert status['count'] == 3
    assert status['enrolled'] is True
    assert status['ready_for_login'] is False


def test_get_H_vector_parsing_and_invalid(db_session, sample_user):
    """KeystrokeVector.get_H_vector should parse JSON strings and preserve lists; invalid JSON returns empty list."""
    from app.models import KeystrokeVector

    # Case 1: H_vector stored as JSON string
    kv1 = KeystrokeVector(
        user_id=sample_user.id,
        H_vector='[0.1, 0.2, 0.3]',
        dd_vector='[0.05, 0.06, 0.07]',
        ud_vector='[0.15, 0.16, 0.17]',
        data_type='enrollment'
    )
    db_session.add(kv1)
    db_session.commit()

    fetched1 = db_session.get(KeystrokeVector, kv1.id)
    assert fetched1.get_H_vector() == [0.1, 0.2, 0.3]

    # Case 2: set via property with list
    kv2 = KeystrokeVector(
        user_id=sample_user.id,
        dd_vector='[0.05, 0.06, 0.07]',
        ud_vector='[0.15, 0.16, 0.17]',
        data_type='enrollment'
    )
    kv2.h_vector = [0.4, 0.5, 0.6]
    db_session.add(kv2)
    db_session.commit()

    fetched2 = db_session.get(KeystrokeVector, kv2.id)
    assert fetched2.get_H_vector() == [0.4, 0.5, 0.6]

    # Case 3: invalid JSON string -> returns empty list
    kv3 = KeystrokeVector(
        user_id=sample_user.id,
        H_vector='not-a-json',
        dd_vector='[0.05, 0.06, 0.07]',
        ud_vector='[0.15, 0.16, 0.17]',
        data_type='enrollment'
    )
    db_session.add(kv3)
    db_session.commit()

    fetched3 = db_session.get(KeystrokeVector, kv3.id)
    assert fetched3.get_H_vector() == []
