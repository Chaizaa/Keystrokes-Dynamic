"""merge multiple heads

Revision ID: c7f1b0b6a9d1
Revises: a1b2c3d4e5f6, 9c1b2d3e4f50
Create Date: 2026-03-05

This is a merge migration to resolve multiple Alembic heads.
It has no schema operations; it just joins the revision graph.
"""

from alembic import op  # noqa: F401


# revision identifiers, used by Alembic.
revision = "c7f1b0b6a9d1"
down_revision = ("a1b2c3d4e5f6", "9c1b2d3e4f50")
branch_labels = None
depends_on = None


def upgrade():
    # No-op: merge point only.
    pass


def downgrade():
    # No-op: merge point only.
    pass
