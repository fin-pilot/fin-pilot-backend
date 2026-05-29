from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.db.models import Category
from app.repositories.category_repository import CategoryRepository
from app.schemas.category import CategoryCreate, CategoryUpdate


class CategoryService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = CategoryRepository(db)

    def list_categories(self, user_id: UUID) -> list[Category]:
        return self._repo.list_for_user(user_id)

    def create_category(
        self,
        user_id: UUID,
        category_in: CategoryCreate,
    ) -> Category:
        category = Category(
            name=category_in.name,
            transaction_type=category_in.type,
            user_id=user_id,
        )
        with self._db.begin():
            self._repo.add(category)
        self._db.refresh(category)
        return category

    def update_category(
        self,
        user_id: UUID,
        category_id: UUID,
        category_in: CategoryUpdate,
    ) -> Category:
        category = self._repo.get_user_category(category_id, user_id)
        if not category:
            raise NotFoundError("Category not found or access denied")

        update_data = category_in.model_dump(exclude_unset=True)
        if "type" in update_data:
            update_data["transaction_type"] = update_data.pop("type")

        if update_data:
            with self._db.begin():
                for key, value in update_data.items():
                    setattr(category, key, value)
            self._db.refresh(category)

        return category

    def delete_category(self, user_id: UUID, category_id: UUID) -> None:
        category = self._repo.get_user_category(category_id, user_id)
        if not category:
            raise NotFoundError("Category not found or access denied")
        with self._db.begin():
            self._repo.delete(category)
