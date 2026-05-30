from __future__ import annotations

from uuid import UUID
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.db.models import Account
from app.repositories.account_repository import AccountRepository
from app.schemas.account import AccountCreate, AccountUpdate


class AccountService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = AccountRepository(db)

    def list_accounts(self, user_id: UUID) -> list[Account]:
        return self._repo.list_by_user(user_id)

    def get_account(self, user_id: UUID, account_id: UUID) -> Account:
        account = self._repo.get_by_id_for_user(account_id, user_id)
        if not account:
            raise NotFoundError("Account not found")
        return account

    def create_account(
        self,
        user_id: UUID,
        account_in: AccountCreate,
    ) -> Account:
        account = Account(
            name=account_in.name,
            account_type=account_in.account_type,
            balance=account_in.balance,
            currency=account_in.currency,
            user_id=user_id,
        )
        
        try:
            self._repo.add(account)
            self._db.commit()
            self._db.refresh(account)
            return account
        except Exception:
            self._db.rollback()
            raise

    def update_account(
        self,
        user_id: UUID,
        account_id: UUID,
        account_in: AccountUpdate,
    ) -> Account:
        account = self._repo.get_by_id_for_user(account_id, user_id)
        if not account:
            raise NotFoundError("Account not found")

        update_data = account_in.model_dump(exclude_unset=True)
        if update_data:
            try:
                for key, value in update_data.items():
                    setattr(account, key, value)
                
                self._db.commit()
                self._db.refresh(account)
            except Exception:
                self._db.rollback()
                raise

        return account

    def delete_account(self, user_id: UUID, account_id: UUID) -> None:
        account = self._repo.get_by_id_for_user(account_id, user_id)
        if not account:
            raise NotFoundError("Account not found")
            
        try:
            self._repo.delete(account)
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise