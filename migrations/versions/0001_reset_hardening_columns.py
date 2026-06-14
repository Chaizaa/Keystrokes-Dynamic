"""Add password_reset_attempts + session_token_version to users.

These back the hardened forgot-password flow:
  * password_reset_attempts — brute-force lockout counter for the 6-digit code.
  * session_token_version    — bumped on reset so stale/stolen sessions die.

The project historically created its schema via ``db.create_all()`` rather than
migrations, so this is the first revision (down_revision=None). It is written to
be idempotent: each column is added only when missing, so it is safe to run
against a legacy DB (columns absent) or a fresh create_all DB (columns present).

Revision ID: 0001_reset_hardening
Revises:
Create Date: 2026-06-13
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0001_reset_hardening"
down_revision = None
branch_labels = None
depends_on = None


def _existing_columns(table: str):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {col["name"] for col in inspector.get_columns(table)}


def upgrade():
    existing = _existing_columns("users")
    with op.batch_alter_table("users") as batch:
        if "password_reset_attempts" not in existing:
            batch.add_column(
                sa.Column(
                    "password_reset_attempts",
                    sa.Integer(),
                    nullable=False,
                    server_default="0",
                )
            )
        if "session_token_version" not in existing:
            batch.add_column(
                sa.Column(
                    "session_token_version",
                    sa.Integer(),
                    nullable=False,
                    server_default="0",
                )
            )


def downgrade():
    existing = _existing_columns("users")
    with op.batch_alter_table("users") as batch:
        if "session_token_version" in existing:
            batch.drop_column("session_token_version")
        if "password_reset_attempts" in existing:
            batch.drop_column("password_reset_attempts")
