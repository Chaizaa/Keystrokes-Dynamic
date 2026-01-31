"""
Add password columns to legacy user_vectors table

Revision ID: g2h3i4adduvpwd
Revises: f1a2b3c4addrole
Create Date: 2026-01-01 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "g2h3i4adduvpwd"
down_revision = "b4f7c9d4a2b8"
branch_labels = None
depends_on = None


def upgrade():
    # Add `password` and `password_hash` to legacy user_vectors table if missing.
    conn = op.get_bind()
    # Check if table exists and which columns are present (SQLite dialect)
    existing_cols = set()
    try:
        res = conn.execute(sa.text("PRAGMA table_info(user_vectors)"))
        for row in res.fetchall():
            # PRAGMA table_info returns rows with 'name' at index 1
            existing_cols.add(row[1])
    except Exception:
        existing_cols = set()

    cols_to_add = []
    if "password" not in existing_cols:
        cols_to_add.append(sa.Column("password", sa.String(length=255), nullable=True))
    if "password_hash" not in existing_cols:
        cols_to_add.append(sa.Column("password_hash", sa.String(length=255), nullable=True))

    if cols_to_add:
        with op.batch_alter_table("user_vectors", schema=None) as batch_op:
            for col in cols_to_add:
                batch_op.add_column(col)


def downgrade():
    conn = op.get_bind()
    existing_cols = set()
    try:
        res = conn.execute(sa.text("PRAGMA table_info(user_vectors)"))
        for row in res.fetchall():
            existing_cols.add(row[1])
    except Exception:
        existing_cols = set()

    with op.batch_alter_table("user_vectors", schema=None) as batch_op:
        if "password_hash" in existing_cols:
            batch_op.drop_column("password_hash")
        if "password" in existing_cols:
            batch_op.drop_column("password")
