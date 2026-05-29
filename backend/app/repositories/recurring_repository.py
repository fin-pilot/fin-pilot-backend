from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import RecurringTransaction


class RecurringRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_by_user(
        self,
        user_id: UUID,
    ) -> list[RecurringTransaction]:
        stmt = select(RecurringTransaction).where(
            RecurringTransaction.user_id == user_id
        )

        return list(self._db.scalars(stmt).all())

    def get_by_id_for_user(
        self,
        recurring_id: UUID,
        user_id: UUID,
    ) -> RecurringTransaction | None:
        stmt = select(RecurringTransaction).where(
            RecurringTransaction.id == recurring_id,
            RecurringTransaction.user_id == user_id,
        )

        return self._db.scalar(stmt)

    def list_due(
        self,
        today: date,
    ) -> list[RecurringTransaction]:
        stmt = select(RecurringTransaction).where(
            RecurringTransaction.is_active,
            RecurringTransaction.next_date <= today,
        )

        return list(self._db.scalars(stmt).all())

    def add(
        self,
        recurring: RecurringTransaction,
    ) -> RecurringTransaction:
        self._db.add(recurring)

        return recurring

    def delete(
        self,
        recurring: RecurringTransaction,
    ) -> None:
        self._db.delete(recurring)
