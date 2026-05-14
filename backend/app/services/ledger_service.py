from __future__ import annotations

from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.core.exceptions import NotFoundError, ValidationError
from backend.app.db.models import Account, Transaction, TransactionType


class LedgerService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def validate_transfer(
        self,
        transaction_type: TransactionType,
        dest_account: Account | None,
    ) -> None:
        if (
            transaction_type == TransactionType.TRANSFER
            and dest_account is None
        ):
            raise ValidationError("Destination account required for transfer.")

    def apply_transaction(
        self,
        account: Account,
        dest_account: Account | None,
        amount: float,
        transaction_type: TransactionType,
    ) -> None:
        self.validate_transfer(transaction_type, dest_account)
        if transaction_type == TransactionType.INCOME:
            account.balance += amount
        elif transaction_type == TransactionType.EXPENSE:
            account.balance -= amount
        elif transaction_type == TransactionType.TRANSFER:
            if dest_account is None:
                raise ValidationError(
                    "Destination account required for transfer."
                )
            account.balance -= amount
            dest_account.balance += amount

    def reverse_transaction(
        self,
        account: Account,
        dest_account: Account | None,
        amount: float,
        transaction_type: TransactionType,
    ) -> None:
        self.validate_transfer(transaction_type, dest_account)
        if transaction_type == TransactionType.INCOME:
            account.balance -= amount
        elif transaction_type == TransactionType.EXPENSE:
            account.balance += amount
        elif transaction_type == TransactionType.TRANSFER:
            if dest_account is None:
                raise ValidationError(
                    "Destination account required for transfer."
                )
            account.balance += amount
            dest_account.balance -= amount

    def update_transaction(
        self,
        account: Account,
        dest_account: Account | None,
        old_amount: float,
        new_amount: float,
        transaction_type: TransactionType,
    ) -> None:
        self.validate_transfer(transaction_type, dest_account)
        difference = new_amount - old_amount
        if difference == 0:
            return
        if transaction_type == TransactionType.INCOME:
            account.balance += difference
        elif transaction_type == TransactionType.EXPENSE:
            account.balance -= difference
        elif transaction_type == TransactionType.TRANSFER:
            if dest_account is None:
                raise ValidationError(
                    "Destination account required for transfer."
                )
            account.balance -= difference
            dest_account.balance += difference

    def recalculate_account_balance(self, account_id: UUID) -> float:
        income_sum = (
            self._db.query(func.coalesce(func.sum(Transaction.amount), 0.0))
            .filter(
                Transaction.account_id == account_id,
                Transaction.transaction_type == TransactionType.INCOME,
            )
            .scalar()
        )
        expense_sum = (
            self._db.query(func.coalesce(func.sum(Transaction.amount), 0.0))
            .filter(
                Transaction.account_id == account_id,
                Transaction.transaction_type == TransactionType.EXPENSE,
            )
            .scalar()
        )
        transfer_out_sum = (
            self._db.query(func.coalesce(func.sum(Transaction.amount), 0.0))
            .filter(
                Transaction.account_id == account_id,
                Transaction.transaction_type == TransactionType.TRANSFER,
            )
            .scalar()
        )
        transfer_in_sum = (
            self._db.query(func.coalesce(func.sum(Transaction.amount), 0.0))
            .filter(Transaction.destination_account_id == account_id)
            .scalar()
        )

        balance = float(income_sum or 0) - float(expense_sum or 0)
        balance -= float(transfer_out_sum or 0)
        balance += float(transfer_in_sum or 0)

        account = (
            self._db.query(Account).filter(Account.id == account_id).first()
        )
        if not account:
            raise NotFoundError("Account not found for recalculation")
        account.balance = balance
        return balance
