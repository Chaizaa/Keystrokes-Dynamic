"""Extend password_hash column to String(256) for werkzeug pbkdf2 hashes

Revision ID: a1b2c3d4e5f6
Revises: e0e42d0e3f98
Create Date: 2026-02-28

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'e0e42d0e3f98'
branch_labels = None
depends_on = None


def _column_exists(table, column):
    bind = op.get_bind()
    cols = [c['name'] for c in sa_inspect(bind).get_columns(table)]
    return column in cols


def upgrade():
    # SQLite batch alter to widen password_hash from String(64) to String(256).
    # Required for werkzeug pbkdf2:sha256 hashes which are ~93 chars.
    # On a fresh DB the column may already be created as Text (SQLite ignores
    # varchar length), but we set the metadata right so Alembic stays in sync.
    if _column_exists('dataset_subjects', 'password_hash'):
        with op.batch_alter_table('dataset_subjects', schema=None) as batch_op:
            batch_op.alter_column(
                'password_hash',
                existing_type=sa.String(length=64),
                type_=sa.String(length=256),
                existing_nullable=True,
            )


def downgrade():
    if _column_exists('dataset_subjects', 'password_hash'):
        with op.batch_alter_table('dataset_subjects', schema=None) as batch_op:
            batch_op.alter_column(
                'password_hash',
                existing_type=sa.String(length=256),
                type_=sa.String(length=64),
                existing_nullable=True,
            )
