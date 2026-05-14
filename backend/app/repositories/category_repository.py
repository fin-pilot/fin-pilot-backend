from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.db.models import Category, TransactionType


class CategoryRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_for_user(self, user_id: UUID) -> list[Category]:
        return (
            self._db.query(Category)
            .filter(
                or_(Category.user_id == user_id, Category.user_id.is_(None))
            )
            .all()
        )

    def get_user_category(
        self,
        category_id: UUID,
        user_id: UUID,
    ) -> Category | None:
        return (
            self._db.query(Category)
            .filter(Category.id == category_id, Category.user_id == user_id)
            .first()
        )

    def get_for_user_or_global(
        self,
        category_id: UUID,
        user_id: UUID,
    ) -> Category | None:
        return (
            self._db.query(Category)
            .filter(
                Category.id == category_id,
                or_(Category.user_id == user_id, Category.user_id.is_(None)),
            )
            .first()
        )

    def find_by_name_for_user_or_global(
        self,
        name: str,
        user_id: UUID,
        transaction_type: TransactionType,
    ) -> Category | None:
        return (
            self._db.query(Category)
            .filter(
                Category.name.ilike(name),
                or_(Category.user_id == user_id, Category.user_id.is_(None)),
                Category.transaction_type == transaction_type,
            )
            .first()
        )

    def get_global_by_name_and_type(
        self,
        name: str,
        transaction_type: TransactionType,
    ) -> Category | None:
        return (
            self._db.query(Category)
            .filter(
                Category.name == name,
                Category.transaction_type == transaction_type,
                Category.user_id.is_(None),
            )
            .first()
        )

    def add(self, category: Category) -> Category:
        self._db.add(category)
        return category

    def delete(self, category: Category) -> None:
        self._db.delete(category)
