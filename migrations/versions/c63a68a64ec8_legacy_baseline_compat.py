"""legacy_baseline_compat

Revision ID: c63a68a64ec8
Revises:
Create Date: 2026-04-15 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c63a68a64ec8"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Compatibility baseline only.
    pass


def downgrade():
    pass
