"""add users.locale and categories.slug columns

Revision ID: d5e6f7a8b9c0
Revises: b3f7a1d9c042
Create Date: 2026-06-01 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d5e6f7a8b9c0"
down_revision = "b3f7a1d9c042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users.locale ──────────────────────────────────────────────────────────
    op.add_column(
        "users",
        sa.Column(
            "locale",
            sa.String(2),
            nullable=False,
            server_default="uk",
        ),
    )

    # ── categories.slug ───────────────────────────────────────────────────────
    op.add_column(
        "categories",
        sa.Column(
            "slug",
            sa.String(64),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_categories_slug",
        "categories",
        ["slug"],
    )


def downgrade() -> None:
    op.drop_index("ix_categories_slug", table_name="categories")
    op.drop_column("categories", "slug")
    op.drop_column("users", "locale")
