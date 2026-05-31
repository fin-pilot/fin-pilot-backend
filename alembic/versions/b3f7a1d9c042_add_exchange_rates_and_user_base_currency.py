"""add exchange_rates table and users.base_currency column

Revision ID: b3f7a1d9c042
Revises: a1b2c3d4e5f6
Create Date: 2026-06-01 00:00:00.000000

"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "b3f7a1d9c042"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users.base_currency ───────────────────────────────────────────────────
    op.add_column(
        "users",
        sa.Column(
            "base_currency",
            sa.String(3),
            nullable=False,
            server_default="UAH",
        ),
    )

    # ── exchange_rates ────────────────────────────────────────────────────────
    op.create_table(
        "exchange_rates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("base_currency", sa.String(3), nullable=False),
        sa.Column("target_currency", sa.String(3), nullable=False),
        sa.Column("rate", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False, server_default="NBU"),
        sa.UniqueConstraint(
            "base_currency",
            "target_currency",
            "rate_date",
            name="uq_exchange_rate_daily",
        ),
    )
    op.create_index(
        "ix_exchange_rates_lookup",
        "exchange_rates",
        ["base_currency", "target_currency", "rate_date"],
    )
    op.create_index(
        "ix_exchange_rates_rate_date",
        "exchange_rates",
        ["rate_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_exchange_rates_rate_date", table_name="exchange_rates")
    op.drop_index("ix_exchange_rates_lookup", table_name="exchange_rates")
    op.drop_table("exchange_rates")
    op.drop_column("users", "base_currency")
