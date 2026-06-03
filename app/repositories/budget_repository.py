from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    Account,
    Budget,
    Transaction,
    TransactionType,
)


class BudgetRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_for_user(self, user_id: UUID) -> list[Budget]:
        """Return user-specific budgets plus global defaults not already overridden.

        When a user has their own budget for a category, the global default for
        that same category is suppressed — the user-specific row wins.
        """
        user_budgets: list[Budget] = list(
            self._db.scalars(
                select(Budget).where(Budget.user_id == user_id)
            ).all()
        )

        overridden_category_ids = {b.category_id for b in user_budgets}

        global_stmt = select(Budget).where(Budget.user_id.is_(None))
        if overridden_category_ids:
            global_stmt = global_stmt.where(
                Budget.category_id.notin_(overridden_category_ids)
            )
        global_budgets: list[Budget] = list(
            self._db.scalars(global_stmt).all()
        )

        return user_budgets + global_budgets

    def get_by_id_for_user(
        self, budget_id: UUID, user_id: UUID
    ) -> Budget | None:
        """Return a budget only if it belongs to the given user (not globals)."""
        return self._db.scalar(
            select(Budget).where(
                Budget.id == budget_id,
                Budget.user_id == user_id,
            )
        )

    def get_by_id_for_user_or_global(
        self, budget_id: UUID, user_id: UUID
    ) -> Budget | None:
        """Return user-specific OR global budget by id."""
        return self._db.scalar(
            select(Budget).where(
                Budget.id == budget_id,
                or_(Budget.user_id == user_id, Budget.user_id.is_(None)),
            )
        )

    def get_spent_amount(
        self,
        user_id: UUID,
        category_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> float:
        stmt = (
            select(func.coalesce(func.sum(Transaction.amount), 0.0))
            .join(Account, Transaction.account_id == Account.id)
            .where(
                Account.user_id == user_id,
                Transaction.category_id == category_id,
                Transaction.transaction_type == TransactionType.EXPENSE,
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date,
            )
        )

        return float(self._db.scalar(stmt) or 0.0)

    def add(self, budget: Budget) -> Budget:
        self._db.add(budget)
        return budget

    def delete(self, budget: Budget) -> None:
        self._db.delete(budget)
