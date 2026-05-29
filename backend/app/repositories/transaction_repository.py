from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select, ColumnElement
from sqlalchemy.orm import Session

from backend.app.db.models import (
    Account,
    Transaction,
    TransactionType,
)


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

        stmt = (
            select(Transaction)
            .join(Transaction.account)
            .where(Account.user_id == user_id)
        )

        conditions: list[ColumnElement[bool]] = []

        if start_date is not None:
            conditions.append(Transaction.transaction_date >= start_date)

        if end_date is not None:
            conditions.append(Transaction.transaction_date <= end_date)

        if account_id is not None:
            conditions.append(Transaction.account_id == account_id)

        if category_id is not None:
            conditions.append(Transaction.category_id == category_id)

        if transaction_type is not None:
            conditions.append(Transaction.transaction_type == transaction_type)

        if conditions:
            stmt = stmt.where(*conditions)

        stmt = (
            stmt.order_by(Transaction.transaction_date.desc())
            .offset(skip)
            .limit(limit)
        )

        return list(self._db.scalars(stmt).all())

    def list_for_user_export(
        self,
        user_id: UUID,
    ) -> list[Transaction]:
        stmt = (
            select(Transaction)
            .join(Account, Transaction.account_id == Account.id)
            .where(Account.user_id == user_id)
            .order_by(Transaction.transaction_date.desc())
        )

        return list(self._db.scalars(stmt).all())

    def get_for_user(
        self,
        transaction_id: UUID,
        user_id: UUID,
    ) -> Transaction | None:
        stmt = (
            select(Transaction)
            .join(Account, Transaction.account_id == Account.id)
            .where(
                Transaction.id == transaction_id,
                Account.user_id == user_id,
            )
        )

        return self._db.scalar(stmt)

    def add(
        self,
        transaction: Transaction,
    ) -> Transaction:
        self._db.add(transaction)

        return transaction

    def delete(
        self,
        transaction: Transaction,
    ) -> None:
        self._db.delete(transaction)
