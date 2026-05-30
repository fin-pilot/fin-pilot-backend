from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.db.models import Budget
from app.repositories.budget_repository import BudgetRepository
from app.repositories.category_repository import CategoryRepository
from app.schemas.budget import (
    BudgetCreate,
    BudgetResponse,
    BudgetUpdate,
)


class BudgetService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = BudgetRepository(db)
        self._categories = CategoryRepository(db)

    def list_budgets(self, user_id: UUID) -> list[BudgetResponse]:
        budgets = self._repo.list_by_user(user_id)
        responses: list[BudgetResponse] = []
        for budget in budgets:
            spent = self._repo.get_spent_amount(
                user_id=user_id,
                category_id=budget.category_id,
                start_date=budget.start_date,
                end_date=budget.end_date,
            )
            responses.append(
                BudgetResponse(
                    id=budget.id,
                    user_id=budget.user_id,
                    category_id=budget.category_id,
                    name=budget.name,
                    limit_amount=budget.limit_amount,
                    start_date=budget.start_date,
                    end_date=budget.end_date,
                    spent_amount=spent,
                )
            )
        return responses

    def create_budget(
        self,
        user_id: UUID,
        budget_in: BudgetCreate,
    ) -> BudgetResponse:
        category = self._categories.get_for_user_or_global(
            budget_in.category_id, user_id
        )
        if not category:
            raise NotFoundError("Category not found")

        name = budget_in.name or category.name
        budget = Budget(
            user_id=user_id,
            category_id=budget_in.category_id,
            name=name,
            limit_amount=budget_in.limit_amount,
            start_date=budget_in.start_date,
            end_date=budget_in.end_date,
        )

        try:
            self._repo.add(budget)
            self._db.commit()
            self._db.refresh(budget)
        except Exception:
            self._db.rollback()
            raise

        return BudgetResponse(
            id=budget.id,
            user_id=budget.user_id,
            category_id=budget.category_id,
            name=budget.name,
            limit_amount=budget.limit_amount,
            start_date=budget.start_date,
            end_date=budget.end_date,
            spent_amount=0.0,
        )

    def update_budget(
        self,
        user_id: UUID,
        budget_id: UUID,
        budget_in: BudgetUpdate,
    ) -> BudgetResponse:
        budget = self._repo.get_by_id_for_user(budget_id, user_id)
        if not budget:
            raise NotFoundError("Budget not found")

        update_data = budget_in.model_dump(exclude_unset=True)
        if update_data:
            try:
                for key, value in update_data.items():
                    setattr(budget, key, value)
                
                self._db.commit()
                self._db.refresh(budget)
            except Exception:
                self._db.rollback()
                raise

        spent = self._repo.get_spent_amount(
            user_id=user_id,
            category_id=budget.category_id,
            start_date=budget.start_date,
            end_date=budget.end_date,
        )

        return BudgetResponse(
            id=budget.id,
            user_id=budget.user_id,
            category_id=budget.category_id,
            name=budget.name,
            limit_amount=budget.limit_amount,
            start_date=budget.start_date,
            end_date=budget.end_date,
            spent_amount=spent,
        )

    def delete_budget(self, user_id: UUID, budget_id: UUID) -> None:
        budget = self._repo.get_by_id_for_user(budget_id, user_id)
        if not budget:
            raise NotFoundError("Budget not found")
            
        try:
            self._repo.delete(budget)
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise