from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.db.models import RecurringTransaction


class RecurringRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_by_user(self, user_id: UUID) -> list[RecurringTransaction]:
        return (
            self._db.query(RecurringTransaction)
            .filter(RecurringTransaction.user_id == user_id)
            .all()
        )

    def get_by_id_for_user(
        self,
        recurring_id: UUID,
        user_id: UUID,
    ) -> RecurringTransaction | None:
        return (
            self._db.query(RecurringTransaction)
            .filter(
                RecurringTransaction.id == recurring_id,
                RecurringTransaction.user_id == user_id,
            )
            .first()
        )

    def list_due(self, today: date) -> list[RecurringTransaction]:
        return (
            self._db.query(RecurringTransaction)
            .filter(
                RecurringTransaction.is_active,
                RecurringTransaction.next_date <= today,
            )
            .all()
        )

    def add(self, recurring: RecurringTransaction) -> RecurringTransaction:
        self._db.add(recurring)
        return recurring

    def delete(self, recurring: RecurringTransaction) -> None:
        self._db.delete(recurring)
