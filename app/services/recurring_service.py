from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import UUID

from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.db.models import (
    RecurringInterval,
    RecurringTransaction,
    Transaction,
    TransactionType,
)
from app.repositories.account_repository import AccountRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.recurring_repository import RecurringRepository
from app.services.ledger_service import LedgerService
from app.schemas.recurring import RecurringCreate, RecurringUpdate


class RecurringService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = RecurringRepository(db)
        self._accounts = AccountRepository(db)
        self._categories = CategoryRepository(db)
        self._ledger = LedgerService(db)

    def list_recurring(self, user_id: UUID) -> list[RecurringTransaction]:
        return self._repo.list_by_user(user_id)

    def get_recurring(
        self,
        user_id: UUID,
        recurring_id: UUID,
    ) -> RecurringTransaction:
        recurring = self._repo.get_by_id_for_user(recurring_id, user_id)
        if not recurring:
            raise NotFoundError("Регулярний платіж не знайдено")
        return recurring

    def create_recurring(
        self,
        user_id: UUID,
        recurring_in: RecurringCreate,
    ) -> RecurringTransaction:
        account = self._accounts.get_by_id_for_user(
            recurring_in.account_id, user_id
        )
        if not account:
            raise NotFoundError("Account not found")

        if recurring_in.category_id is not None:
            category = self._categories.get_for_user_or_global(
                recurring_in.category_id, user_id
            )
            if not category:
                raise NotFoundError("Category not found")

        tx_type = self._parse_transaction_type(recurring_in.type)
        if tx_type == TransactionType.TRANSFER:
            raise ValidationError(
                "Transfers are not supported for recurring transactions"
            )

        start_date = recurring_in.start_date or date.today()
        recurring = RecurringTransaction(
            user_id=user_id,
            account_id=recurring_in.account_id,
            category_id=recurring_in.category_id,
            description=recurring_in.description,
            amount=recurring_in.amount,
            transaction_type=tx_type,
            interval=recurring_in.interval,
            start_date=start_date,
            next_date=start_date,
        )

        try:
            self._repo.add(recurring)
            self._db.commit()
            self._db.refresh(recurring)
            return recurring
        except Exception:
            self._db.rollback()
            raise

    def update_recurring(
        self,
        user_id: UUID,
        recurring_id: UUID,
        recurring_in: RecurringUpdate,
    ) -> RecurringTransaction:
        recurring = self._repo.get_by_id_for_user(recurring_id, user_id)
        if not recurring:
            raise NotFoundError("Регулярний платіж не знайдено")

        update_data = recurring_in.model_dump(exclude_unset=True)
        if update_data:
            try:
                for key, value in update_data.items():
                    setattr(recurring, key, value)
                
                self._db.commit()
                self._db.refresh(recurring)
            except Exception:
                self._db.rollback()
                raise

        return recurring

    def delete_recurring(self, user_id: UUID, recurring_id: UUID) -> None:
        recurring = self._repo.get_by_id_for_user(recurring_id, user_id)
        if not recurring:
            raise NotFoundError("Регулярний платіж не знайдено")
            
        try:
            self._repo.delete(recurring)
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

    def process_due(self, today: date | None = None) -> int:
        target_date = today or date.today()
        due_subscriptions = self._repo.list_due(target_date)
        if not due_subscriptions:
            return 0

        now = datetime.now().astimezone()
        
        try:
            for sub in due_subscriptions:
                account = self._accounts.get_by_id(sub.account_id)
                if not account:
                    raise NotFoundError("Account not found for recurring item")

                transaction = Transaction(
                    account_id=sub.account_id,
                    category_id=sub.category_id,
                    description=f"[Subscription] {sub.description}",
                    amount=sub.amount,
                    transaction_type=sub.transaction_type,
                    transaction_date=now,
                )
                self._db.add(transaction)

                self._ledger.apply_transaction(
                    account,
                    None,
                    sub.amount,
                    sub.transaction_type,
                )
                self._advance_next_date(sub)
                
            # Commit the entire batch of recurring transactions at once
            self._db.commit()
            
        except Exception:
            # If any single subscription fails, roll them all back
            self._db.rollback()
            raise

        return len(due_subscriptions)

    @staticmethod
    def _advance_next_date(sub: RecurringTransaction) -> None:
        if sub.interval == RecurringInterval.DAILY:
            sub.next_date = sub.next_date + timedelta(days=1)
        elif sub.interval == RecurringInterval.WEEKLY:
            sub.next_date = sub.next_date + timedelta(weeks=1)
        elif sub.interval == RecurringInterval.MONTHLY:
            sub.next_date = sub.next_date + relativedelta(months=1)
        elif sub.interval == RecurringInterval.YEARLY:
            sub.next_date = sub.next_date + relativedelta(years=1)

    @staticmethod
    def _parse_transaction_type(
        raw: TransactionType | str,
    ) -> TransactionType:
        if isinstance(raw, TransactionType):
            return raw
        key = raw.strip().lower()
        mapping = {
            "income": TransactionType.INCOME,
            "expense": TransactionType.EXPENSE,
            "transfer": TransactionType.TRANSFER,
        }
        if key not in mapping:
            raise ValidationError(f"Unknown transaction_type: {raw!r}")
        return mapping[key]


def process_recurring_transactions(db: Session) -> int:
    return RecurringService(db).process_due()