"""Add API key management and logging tables

Revision ID: 2cb60a1efd73
Revises: g2h3i4adduvpwd
Create Date: 2026-03-06 17:39:31.151752

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2cb60a1efd73'
down_revision = 'g2h3i4adduvpwd'
branch_labels = None
depends_on = None


def upgrade():
    # ### Create API Keys Table ###
    op.create_table('api_keys',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('partner_name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('key_prefix', sa.String(length=20), nullable=False),
    sa.Column('key_hash', sa.String(length=255), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
    sa.Column('rate_limit', sa.Integer(), nullable=False, server_default=sa.text('100')),
    sa.Column('enrolled_users', sa.Integer(), nullable=False, server_default=sa.text('0')),
    sa.Column('total_enrollments', sa.Integer(), nullable=False, server_default=sa.text('0')),
    sa.Column('total_verifications', sa.Integer(), nullable=False, server_default=sa.text('0')),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('last_used_at', sa.DateTime(), nullable=True),
    sa.Column('expires_at', sa.DateTime(), nullable=True),
    sa.Column('allowed_origins', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_api_keys_partner_active', 'api_keys', ['partner_name', 'is_active'], unique=False)
    op.create_index('idx_api_keys_user_active', 'api_keys', ['user_id', 'is_active'], unique=False)
    op.create_index('idx_api_keys_prefix', 'api_keys', ['key_prefix'], unique=False)

    # ### Create Enrollment Logs Table ###
    op.create_table('enrollment_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('api_key_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('username', sa.String(length=80), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('samples_count', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False, server_default=sa.text("'pending'")),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('enrollment_id', sa.String(length=100), nullable=True),
    sa.Column('client_ip', sa.String(length=45), nullable=True),
    sa.Column('user_agent', sa.String(length=255), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['api_key_id'], ['api_keys.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('enrollment_id')
    )
    op.create_index('idx_enrollment_api_key_timestamp', 'enrollment_logs', ['api_key_id', 'timestamp'], unique=False)
    op.create_index('idx_enrollment_user_timestamp', 'enrollment_logs', ['user_id', 'timestamp'], unique=False)
    op.create_index('idx_enrollment_username_timestamp', 'enrollment_logs', ['username', 'timestamp'], unique=False)
    op.create_index('idx_enrollment_status', 'enrollment_logs', ['status'], unique=False)

    # ### Create Verification Logs Table ###
    op.create_table('verification_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('api_key_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('username', sa.String(length=80), nullable=False),
    sa.Column('verified', sa.Boolean(), nullable=False),
    sa.Column('confidence_score', sa.Float(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('client_ip', sa.String(length=45), nullable=True),
    sa.Column('user_agent', sa.String(length=255), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['api_key_id'], ['api_keys.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_verification_api_key_timestamp', 'verification_logs', ['api_key_id', 'timestamp'], unique=False)
    op.create_index('idx_verification_user_timestamp', 'verification_logs', ['user_id', 'timestamp'], unique=False)
    op.create_index('idx_verification_username_timestamp', 'verification_logs', ['username', 'timestamp'], unique=False)
    op.create_index('idx_verification_verified', 'verification_logs', ['verified'], unique=False)


def downgrade():
    # ### Drop Verification Logs Table ###
    op.drop_index('idx_verification_verified', table_name='verification_logs')
    op.drop_index('idx_verification_username_timestamp', table_name='verification_logs')
    op.drop_index('idx_verification_user_timestamp', table_name='verification_logs')
    op.drop_index('idx_verification_api_key_timestamp', table_name='verification_logs')
    op.drop_table('verification_logs')

    # ### Drop Enrollment Logs Table ###
    op.drop_index('idx_enrollment_status', table_name='enrollment_logs')
    op.drop_index('idx_enrollment_username_timestamp', table_name='enrollment_logs')
    op.drop_index('idx_enrollment_user_timestamp', table_name='enrollment_logs')
    op.drop_index('idx_enrollment_api_key_timestamp', table_name='enrollment_logs')
    op.drop_table('enrollment_logs')

    # ### Drop API Keys Table ###
    op.drop_index('idx_api_keys_prefix', table_name='api_keys')
    op.drop_index('idx_api_keys_user_active', table_name='api_keys')
    op.drop_index('idx_api_keys_partner_active', table_name='api_keys')
    op.drop_table('api_keys')
