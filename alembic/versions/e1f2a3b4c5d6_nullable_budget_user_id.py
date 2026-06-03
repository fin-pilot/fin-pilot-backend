"""make budgets.user_id nullable for system-default budgets

Revision ID: e1f2a3b4c5d6
Revises: d5e6f7a8b9c0
Create Date: 2026-06-03 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "e1f2a3b4c5d6"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("budgets", "user_id", nullable=True)


def downgrade() -> None:
    # Remove any system-default rows before restoring NOT NULL
    op.execute("DELETE FROM budgets WHERE user_id IS NULL")
    op.alter_column("budgets", "user_id", nullable=False)
