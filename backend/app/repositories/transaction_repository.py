from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.db.models import Account, Transaction, TransactionType


class TransactionRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_for_user(
        self,
        user_id: UUID,
        *,
        skip: int,
        limit: int,
        start_date: date | None,
        end_date: date | None,
        account_id: UUID | None,
        category_id: UUID | None,
        transaction_type: TransactionType | None,
    ) -> list[Transaction]:
        query = (
            self._db.query(Transaction)
            .join(Account, Transaction.account_id == Account.id)
            .filter(Account.user_id == user_id)
        )

        if start_date:
            query = query.filter(Transaction.transaction_date >= start_date)

        if end_date:
            query = query.filter(Transaction.transaction_date <= end_date)

        if account_id:
            query = query.filter(Transaction.account_id == account_id)

        if category_id:
            query = query.filter(Transaction.category_id == category_id)

        if transaction_type:
            query = query.filter(
                Transaction.transaction_type == transaction_type
            )

        return (
            query.order_by(Transaction.transaction_date.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_for_user_export(self, user_id: UUID) -> list[Transaction]:
        return (
            self._db.query(Transaction)
            .join(Account, Transaction.account_id == Account.id)
            .filter(Account.user_id == user_id)
            .order_by(Transaction.transaction_date.desc())
            .all()
        )

    def get_for_user(
        self, transaction_id: UUID, user_id: UUID
    ) -> Transaction | None:
        return (
            self._db.query(Transaction)
            .join(Account, Transaction.account_id == Account.id)
            .filter(
                Transaction.id == transaction_id, Account.user_id == user_id
            )
            .first()
        )

    def add(self, transaction: Transaction) -> Transaction:
        self._db.add(transaction)
        return transaction

    def delete(self, transaction: Transaction) -> None:
        self._db.delete(transaction)
