from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import Category, TransactionType


class CategoryRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_for_user(self, user_id: UUID) -> list[Category]:
        stmt = select(Category).where(
            or_(Category.user_id == user_id, Category.user_id.is_(None))
        )

        return list(self._db.scalars(stmt).all())

    def get_user_category(
        self, category_id: UUID, user_id: UUID
    ) -> Category | None:
        stmt = select(Category).where(
            Category.id == category_id,
            Category.user_id == user_id,
        )

        return self._db.scalar(stmt)

    def get_for_user_or_global(
        self, category_id: UUID, user_id: UUID
    ) -> Category | None:
        stmt = select(Category).where(
            Category.id == category_id,
            or_(Category.user_id == user_id, Category.user_id.is_(None)),
        )

        return self._db.scalar(stmt)

    def find_by_name_for_user_or_global(
        self, name: str, user_id: UUID, transaction_type: TransactionType
    ) -> Category | None:
        stmt = select(Category).where(
            Category.name.ilike(name),
            or_(Category.user_id == user_id, Category.user_id.is_(None)),
            Category.transaction_type == transaction_type,
        )

        return self._db.scalar(stmt)

    def get_global_by_name_and_type(
        self, name: str, transaction_type: TransactionType
    ) -> Category | None:
        stmt = select(Category).where(
            Category.name == name,
            Category.transaction_type == transaction_type,
            Category.user_id.is_(None),
        )

        return self._db.scalar(stmt)

    def add(self, category: Category) -> Category:
        self._db.add(category)

        return category

    def delete(self, category: Category) -> None:
        self._db.delete(category)
