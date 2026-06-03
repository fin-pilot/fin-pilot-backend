from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.db.models import Budget
from app.repositories.budget_repository import BudgetRepository
from app.repositories.category_repository import CategoryRepository
from app.schemas.budget import (
    BudgetCreate,
    BudgetResponse,
    BudgetUpdate,
)

# Sentinel dates written to DB for global default budgets.
_SENTINEL_START = datetime(2000, 1, 1, tzinfo=timezone.utc)


def _current_month_bounds() -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_day = monthrange(now.year, now.month)[1]
    end = now.replace(
        day=last_day, hour=23, minute=59, second=59, microsecond=0
    )
    return start, end


def _is_default(budget: Budget) -> bool:
    return budget.user_id is None


def _build_response(
    budget: Budget,
    spent: float,
    *,
    effective_start: datetime,
    effective_end: datetime,
) -> BudgetResponse:
    return BudgetResponse(
        id=budget.id,
        user_id=budget.user_id,
        category_id=budget.category_id,
        name=budget.name,
        limit_amount=float(budget.limit_amount),
        start_date=effective_start,
        end_date=effective_end,
        spent_amount=spent,
        is_default=_is_default(budget),
    )


class BudgetService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = BudgetRepository(db)
        self._categories = CategoryRepository(db)

    def list_budgets(self, user_id: UUID) -> list[BudgetResponse]:
        budgets = self._repo.list_for_user(user_id)
        month_start, month_end = _current_month_bounds()
        responses: list[BudgetResponse] = []

        for budget in budgets:
            # Global defaults use current-month bounds for spent calculation
            # and display — sentinel dates would confuse the frontend.
            if _is_default(budget):
                eff_start, eff_end = month_start, month_end
            else:
                eff_start, eff_end = budget.start_date, budget.end_date

            spent = self._repo.get_spent_amount(
                user_id=user_id,
                category_id=budget.category_id,
                start_date=eff_start,
                end_date=eff_end,
            )
            responses.append(
                _build_response(
                    budget,
                    spent,
                    effective_start=eff_start,
                    effective_end=eff_end,
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

        return _build_response(
            budget,
            0.0,
            effective_start=budget.start_date,
            effective_end=budget.end_date,
        )

    def update_budget(
        self,
        user_id: UUID,
        budget_id: UUID,
        budget_in: BudgetUpdate,
    ) -> BudgetResponse:
        budget = self._repo.get_by_id_for_user_or_global(budget_id, user_id)
        if not budget:
            raise NotFoundError("Budget not found")

        update_data = budget_in.model_dump(exclude_unset=True)

        if _is_default(budget):
            # Copy-on-write: materialise a user-specific row from the default.
            # Dates fall back to current month if the client does not supply them.
            month_start, month_end = _current_month_bounds()
            new_budget = Budget(
                user_id=user_id,
                category_id=budget.category_id,
                name=update_data.get("name", budget.name),
                limit_amount=update_data.get(
                    "limit_amount", float(budget.limit_amount)
                ),
                start_date=update_data.get("start_date", month_start),
                end_date=update_data.get("end_date", month_end),
            )
            try:
                self._repo.add(new_budget)
                self._db.commit()
                self._db.refresh(new_budget)
            except Exception:
                self._db.rollback()
                raise
            budget = new_budget
        else:
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
        return _build_response(
            budget,
            spent,
            effective_start=budget.start_date,
            effective_end=budget.end_date,
        )

    def delete_budget(self, user_id: UUID, budget_id: UUID) -> None:
        # Only user-specific budgets may be deleted; global defaults are shared.
        budget = self._repo.get_by_id_for_user(budget_id, user_id)
        if not budget:
            raise NotFoundError(
                "Budget not found. System-default budgets cannot be deleted."
            )

        try:
            self._repo.delete(budget)
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
