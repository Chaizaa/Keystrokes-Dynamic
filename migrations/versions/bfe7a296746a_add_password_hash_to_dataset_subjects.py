"""add_password_hash_to_dataset_subjects

Revision ID: bfe7a296746a
Revises: 877b4444fe94
Create Date: 2026-02-28 14:11:43.255012

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


# revision identifiers, used by Alembic.
revision = 'bfe7a296746a'
down_revision = '877b4444fe94'
branch_labels = None
depends_on = None


def _column_exists(table, column):
    bind = op.get_bind()
    try:
        cols = [c['name'] for c in sa_inspect(bind).get_columns(table)]
    except Exception:
        return False
    return column in cols


def _table_exists(table):
    bind = op.get_bind()
    try:
        return table in sa_inspect(bind).get_table_names()
    except Exception:
        return False


def upgrade():
    # Only alter target_phrase if it exists (old local DB).
    # On a fresh DB (Railway) the column was never created.
    if _table_exists('dataset_entries') and _column_exists('dataset_entries', 'target_phrase'):
        with op.batch_alter_table('dataset_entries', schema=None) as batch_op:
            batch_op.alter_column('target_phrase',
                   existing_type=sa.VARCHAR(length=50),
                   nullable=True)

    if _table_exists('dataset_subjects'):
        with op.batch_alter_table('dataset_subjects', schema=None) as batch_op:
            if not _column_exists('dataset_subjects', 'password_hash'):
                batch_op.add_column(sa.Column('password_hash', sa.String(length=64), nullable=True))


def downgrade():
    if _table_exists('dataset_subjects') and _column_exists('dataset_subjects', 'password_hash'):
        with op.batch_alter_table('dataset_subjects', schema=None) as batch_op:
            batch_op.drop_column('password_hash')

    if _table_exists('dataset_entries') and _column_exists('dataset_entries', 'target_phrase'):
        with op.batch_alter_table('dataset_entries', schema=None) as batch_op:
            batch_op.alter_column('target_phrase',
                   existing_type=sa.VARCHAR(length=50),
                   nullable=False)
