from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
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

    def list_by_user(self, user_id: UUID) -> list[Budget]:
        stmt = select(Budget).where(Budget.user_id == user_id)

        return list(self._db.scalars(stmt).all())

    def get_by_id_for_user(
        self, budget_id: UUID, user_id: UUID
    ) -> Budget | None:
        stmt = select(Budget).where(
            Budget.id == budget_id, Budget.user_id == user_id
        )

        return self._db.scalar(stmt)

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

        spent = self._db.scalar(stmt)

        return float(spent or 0.0)

    def add(self, budget: Budget) -> Budget:
        self._db.add(budget)

        return budget

    def delete(self, budget: Budget) -> None:
        self._db.delete(budget)
