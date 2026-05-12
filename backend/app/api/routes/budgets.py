from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from uuid import UUID

from app.db.database import get_db
from app.db.models import (
    Account,
    Budget,
    Category,
    Transaction,
    TransactionType,
    User,
)
from app.schemas.budget import BudgetCreate, BudgetResponse, BudgetUpdate
from app.api.dependencies import get_current_user

router = APIRouter(prefix="/api/budgets", tags=["budgets"])


@router.get("/", response_model=List[BudgetResponse])
def get_budgets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    budgets = db.query(Budget).filter(Budget.user_id == current_user.id).all()

    for budget in budgets:
        spent = (
            db.query(func.sum(Transaction.amount))
            .join(Account, Transaction.account_id == Account.id)
            .filter(
                Account.user_id == current_user.id,
                Transaction.category_id == budget.category_id,
                Transaction.transaction_type == TransactionType.EXPENSE,
                Transaction.transaction_date >= budget.start_date,
                Transaction.transaction_date <= budget.end_date,
            )
            .scalar()
        )

        budget.spent_amount = spent if spent else 0.0

    return budgets


@router.post(
    "/", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED
)
def create_budget(
    budget_in: BudgetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    category = (
        db.query(Category)
        .filter(
            Category.id == budget_in.category_id,
            (Category.user_id == current_user.id) | (Category.user_id is None),
        )
        .first()
    )

    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    new_budget = Budget(**budget_in.model_dump(), user_id=current_user.id)
    db.add(new_budget)
    db.commit()
    db.refresh(new_budget)

    new_budget.spent_amount = 0.0
    return new_budget


@router.put("/{budget_id}", response_model=BudgetResponse)
def update_budget(
    budget_id: UUID,
    budget_in: BudgetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    budget = (
        db.query(Budget)
        .filter(Budget.id == budget_id, Budget.user_id == current_user.id)
        .first()
    )
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    update_data = budget_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(budget, key, value)

    db.commit()
    db.refresh(budget)

    spent = (
        db.query(func.sum(Transaction.amount))
        .join(Account, Transaction.account_id == Account.id)
        .filter(
            Account.user_id == current_user.id,
            Transaction.category_id == budget.category_id,
            Transaction.transaction_type == TransactionType.EXPENSE,
            Transaction.transaction_date >= budget.start_date,
            Transaction.transaction_date <= budget.end_date,
        )
        .scalar()
    )
    budget.spent_amount = spent if spent else 0.0

    return budget


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(
    budget_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    budget = (
        db.query(Budget)
        .filter(Budget.id == budget_id, Budget.user_id == current_user.id)
        .first()
    )
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    db.delete(budget)
    db.commit()
    return None
