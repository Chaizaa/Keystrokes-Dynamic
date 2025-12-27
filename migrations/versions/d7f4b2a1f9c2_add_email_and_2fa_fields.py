"""
Add email verification and two-factor fields to users table

Revision ID: d7f4b2a1f9c2
Revises: c63a68a64ec8
Create Date: 2025-12-27 00:40:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd7f4b2a1f9c2'
down_revision = 'c63a68a64ec8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('email_verified', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('email_verification_token', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('email_verification_sent_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('two_factor_enabled', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('two_factor_secret', sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('two_factor_secret')
        batch_op.drop_column('two_factor_enabled')
        batch_op.drop_column('email_verification_sent_at')
        batch_op.drop_column('email_verification_token')
        batch_op.drop_column('email_verified')
        batch_op.drop_column('email')
