"""add user_ml_states table

Revision ID: a1b2c3d4e5f6
Revises: c5c8d00ea6eb
Create Date: 2026-05-31 00:00:00.000000

"""

from __future__ import annotations

import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "c5c8d00ea6eb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_ml_states",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "training_status",
            sa.Enum(
                "pending",
                "training",
                "ready",
                "failed",
                name="mltrainingstatus",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("sarima_model_path", sa.String(), nullable=True),
        sa.Column("n_training_samples", sa.Integer(), nullable=True),
        sa.Column(
            "last_trained_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("error_message", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_user_ml_states_user_id",
        "user_ml_states",
        ["user_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_user_ml_states_user_id", table_name="user_ml_states")
    op.drop_table("user_ml_states")
    op.execute("DROP TYPE IF EXISTS mltrainingstatus")
