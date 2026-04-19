"""add_unique_constraint_entry_subject_session_rep

Revision ID: 3f6ad6c3c98f
Revises: bfe7a296746a
Create Date: 2026-02-28 15:16:15.814062

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


# revision identifiers, used by Alembic.
revision = '3f6ad6c3c98f'
down_revision = 'bfe7a296746a'
branch_labels = None
depends_on = None


def _column_exists(table, column):
    bind = op.get_bind()
    try:
        cols = [c['name'] for c in sa_inspect(bind).get_columns(table)]
    except Exception:
        return False
    return column in cols


def upgrade():
    # Only create this constraint if session_no exists (old local DB).
    # On a fresh DB (Railway) session_no was never created.
    if _column_exists('dataset_entries', 'session_no'):
        with op.batch_alter_table('dataset_entries', schema=None) as batch_op:
            batch_op.create_unique_constraint(
                'uq_entry_subject_session_rep',
                ['subject_id', 'session_no', 'repetition']
            )


def downgrade():
    if _column_exists('dataset_entries', 'session_no'):
        with op.batch_alter_table('dataset_entries', schema=None) as batch_op:
            batch_op.drop_constraint('uq_entry_subject_session_rep', type_='unique')
