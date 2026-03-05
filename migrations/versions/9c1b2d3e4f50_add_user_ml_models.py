"""add_user_ml_models

Revision ID: 9c1b2d3e4f50
Revises: 3f6ad6c3c98f
Create Date: 2026-03-05

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9c1b2d3e4f50"
down_revision = "3f6ad6c3c98f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_ml_models",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("model_blob", sa.LargeBinary(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("feature_names_json", sa.Text(), nullable=False),
        sa.Column(
            "model_type",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'RandomForestClassifier'"),
        ),
        sa.Column("sklearn_version", sa.Text(), nullable=True),
        sa.Column("metrics_json", sa.Text(), nullable=True),
        sa.Column("train_params_json", sa.Text(), nullable=True),
        sa.Column("n_samples_total", sa.Integer(), nullable=True),
        sa.Column("n_genuine", sa.Integer(), nullable=True),
        sa.Column("n_impostor", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_user_ml_models_user_id"),
        sa.UniqueConstraint("username", name="uq_user_ml_models_username"),
    )

    op.create_index("ix_user_ml_models_user_id", "user_ml_models", ["user_id"])
    op.create_index("ix_user_ml_models_username", "user_ml_models", ["username"])


def downgrade():
    op.drop_index("ix_user_ml_models_username", table_name="user_ml_models")
    op.drop_index("ix_user_ml_models_user_id", table_name="user_ml_models")
    op.drop_table("user_ml_models")
