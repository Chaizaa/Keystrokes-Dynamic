"""drop_target_phrase_session_no_global_rep

Revision ID: e0e42d0e3f98
Revises: 3f6ad6c3c98f
Create Date: 2026-02-28 15:34:37.575167

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


# revision identifiers, used by Alembic.
revision = 'e0e42d0e3f98'
down_revision = '3f6ad6c3c98f'
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
    if not _table_exists('dataset_entries'):
        return

    with op.batch_alter_table('dataset_entries', schema=None) as batch_op:
        # Drop old index/constraint only if the columns still exist (old local DB).
        # On a fresh DB (Railway) these were never created.
        if _column_exists('dataset_entries', 'session_no'):
            batch_op.drop_index(batch_op.f('ix_dataset_entries_session_no'))
            batch_op.drop_constraint(
                batch_op.f('uq_entry_subject_session_rep'), type_='unique'
            )
            batch_op.drop_column('session_no')
        if _column_exists('dataset_entries', 'target_phrase'):
            batch_op.drop_column('target_phrase')
        # Always ensure the new unique constraint exists.
        batch_op.create_unique_constraint(
            'uq_entry_subject_rep', ['subject_id', 'repetition']
        )


def downgrade():
    if not _table_exists('dataset_entries'):
        return

    with op.batch_alter_table('dataset_entries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('target_phrase', sa.VARCHAR(length=50), nullable=True))
        batch_op.add_column(sa.Column('session_no', sa.INTEGER(), nullable=False))
        batch_op.drop_constraint('uq_entry_subject_rep', type_='unique')
        batch_op.create_unique_constraint(
            batch_op.f('uq_entry_subject_session_rep'),
            ['subject_id', 'session_no', 'repetition']
        )
        batch_op.create_index(
            batch_op.f('ix_dataset_entries_session_no'), ['session_no'], unique=False
        )
