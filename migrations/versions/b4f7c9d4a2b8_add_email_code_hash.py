"""Add email_verification_code_hash column to users table

Revision ID: b4f7c9d4a2b8
Revises: f1a2b3c4addrole
Create Date: 2025-12-27 14:30:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b4f7c9d4a2b8'
down_revision = 'f1a2b3c4addrole'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('email_verification_code_hash', sa.String(length=128), nullable=True))


def downgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('email_verification_code_hash')
