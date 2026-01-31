"""
Remove stored email verification token and legacy plain_password from users table

Revision ID: e3b9c8d5f4b1
Revises: d7f4b2a1f9c2
Create Date: 2025-12-27 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e3b9c8d5f4b1"
down_revision = "d7f4b2a1f9c2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        # Drop legacy plain_password column if it exists
        try:
            batch_op.drop_column("plain_password")
        except Exception:
            pass
        # Drop stored email verification token column (we switched to stateless tokens)
        try:
            batch_op.drop_column("email_verification_token")
        except Exception:
            pass


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        # Re-create columns in downgrade (best-effort, may be NULLable)
        try:
            batch_op.add_column(sa.Column("plain_password", sa.String(length=255), nullable=True))
        except Exception:
            pass
        try:
            batch_op.add_column(
                sa.Column("email_verification_token", sa.String(length=255), nullable=True)
            )
        except Exception:
            pass
