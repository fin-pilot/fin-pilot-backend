"""seed_default_categories

Revision ID: a6715d1801a3
Revises: ae89015fb7ab
Create Date: 2026-05-12 23:51:52.169669

"""

from typing import Sequence, Union, UUID
import uuid

from alembic import op
import sqlalchemy as sa

revision: str = "a6715d1801a3"
down_revision: Union[str, Sequence[str], None] = "ae89015fb7ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

category_table = sa.table(
    "category",
    sa.column("id", UUID(as_uuid=True)),
    sa.column("name", sa.String),
    sa.column("transaction_type", sa.String),
    sa.column("user_id", UUID(as_uuid=True)),
    sa.column("color", sa.String),
    sa.column("icon", sa.String),
)


def upgrade() -> None:
    expense_categories = [
        "Auto & Transport",
        "Bills & Utilities",
        "Entertainment",
        "Fees & Charges",
        "Food & Dining",
        "Groceries",
        "Health & Fitness",
        "Home",
        "Kids",
        "Misc Expenses",
        "Personal Care",
        "Pets",
        "Shopping",
        "Taxes",
        "Travel",
        "Other",
    ]

    income_categories = [
        "Income",
        "Investments",
        "Salary",
        "Other",
    ]

    seed_data = []

    for name in expense_categories:
        seed_data.append(
            {
                "id": uuid.uuid4(),
                "name": name,
                "transaction_type": "EXPENSE",
                "user_id": None,
                "color": "#808080" if name == "Other" else "#000000",
                "icon": "mdi-help-circle" if name == "Other" else "mdi-shape",
            }
        )

    for name in income_categories:
        seed_data.append(
            {
                "id": uuid.uuid4(),
                "name": name,
                "transaction_type": "INCOME",
                "user_id": None,
                "color": "#808080" if name == "Other" else "#008000",
                "icon": "mdi-cash" if name == "Other" else "mdi-cash-multiple",
            }
        )

    op.bulk_insert(category_table, seed_data)


def downgrade() -> None:
    op.execute("DELETE FROM category WHERE user_id IS NULL")
