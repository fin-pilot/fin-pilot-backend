from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.db.models import Account


class AccountRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_by_user(self, user_id: UUID) -> list[Account]:
        return self._db.query(Account).filter(Account.user_id == user_id).all()

    def get_by_id(self, account_id: UUID) -> Account | None:
        return self._db.query(Account).filter(Account.id == account_id).first()

    def get_by_id_for_user(
        self,
        account_id: UUID,
        user_id: UUID,
    ) -> Account | None:
        return (
            self._db.query(Account)
            .filter(Account.id == account_id, Account.user_id == user_id)
            .first()
        )

    def add(self, account: Account) -> Account:
        self._db.add(account)
        return account

    def delete(self, account: Account) -> None:
        self._db.delete(account)
