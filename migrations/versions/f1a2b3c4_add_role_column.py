"""
Add role column to users table

Revision ID: f1a2b3c4addrole
Revises: e3b9c8d5f4b1
Create Date: 2025-12-27 00:50:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f1a2b3c4addrole'
down_revision = 'e3b9c8d5f4b1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('role', sa.String(length=10), nullable=False, server_default=sa.text("'user'")))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('role')
