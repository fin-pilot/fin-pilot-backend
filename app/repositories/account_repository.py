from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Account


class AccountRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_by_user(self, user_id: UUID) -> list[Account]:
        stmt = select(Account).where(Account.user_id == user_id)
        return list(self._db.scalars(stmt).all())

    def get_by_id(self, account_id: UUID) -> Account | None:
        stmt = select(Account).where(Account.id == account_id)
        return self._db.scalar(stmt)

    def get_by_id_for_user(
        self, account_id: UUID, user_id: UUID
    ) -> Account | None:
        stmt = select(Account).where(
            Account.id == account_id, Account.user_id == user_id
        )

        return self._db.scalar(stmt)

    def add(self, account: Account) -> Account:
        self._db.add(account)
        return account

    def delete(self, account: Account) -> None:
        self._db.delete(account)
