"""
Test that frontend-friendly mapping would be used for migration/schema messages.
This test simulates the API response and checks our intended JS mapping logic in a small helper.
Note: This is a quick unit-style test to validate the mapping logic in Python (mirror of client regex).
"""

import re

migrationPattern = re.compile(r"alembic|schema|database schema|run alembic|no (?:such )?column|has no column", re.IGNORECASE)


def friendly_message(server_msg: str) -> str:
    if migrationPattern.search(server_msg):
        return 'Registration temporarily unavailable. Please try again later.'
    return server_msg


def test_friendly_message_maps_migration_texts():
    assert friendly_message('Unable to create account: database schema out of date (run alembic upgrade)') == 'Registration temporarily unavailable. Please try again later.'
    assert friendly_message('Table users has no column named email') == 'Registration temporarily unavailable. Please try again later.'
    assert friendly_message('Password salah') == 'Password salah'