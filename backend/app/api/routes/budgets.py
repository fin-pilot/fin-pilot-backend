from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from uuid import UUID

from backend.app.db.database import get_db
from backend.app.db.models import (
    Account,
    Budget,
    Category,
    Transaction,
    TransactionType,
    User,
)
from backend.app.schemas.budget import (
    BudgetCreate,
    BudgetResponse,
    BudgetUpdate,
)
from backend.app.api.dependencies import get_current_user

router = APIRouter(prefix="/api/budgets", tags=["budgets"])


@router.get("/", response_model=list[BudgetResponse])
def get_budgets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    budgets = db.query(Budget).filter(Budget.user_id == current_user.id).all()

    if not budgets:
        return []

    budget_responses = []

    for budget in budgets:
        spent = db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0.0))
            .join(Account, Transaction.account_id == Account.id)
            .where(
                Account.user_id == current_user.id,
                Transaction.category_id == budget.category_id,
                Transaction.transaction_type == TransactionType.EXPENSE,
                Transaction.transaction_date >= budget.start_date,
                Transaction.transaction_date <= budget.end_date,
            )
        ).scalar_one()

        budget_responses.append(
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

    return budget_responses


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
            (
                (Category.user_id == current_user.id)
                | (Category.user_id.is_(None))
            ),
        )
        .first()
    )

    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    new_budget = Budget(**budget_in.model_dump(), user_id=current_user.id)
    db.add(new_budget)
    db.commit()
    db.refresh(new_budget)

    return BudgetResponse(
        id=new_budget.id,
        user_id=new_budget.user_id,
        category_id=new_budget.category_id,
        name=new_budget.name,
        limit_amount=new_budget.limit_amount,
        start_date=new_budget.start_date,
        end_date=new_budget.end_date,
        spent_amount=0.0,
    )


@router.put("/{budget_id}", response_model=BudgetResponse)
def update_budget(
    budget_id: UUID,
    budget_in: BudgetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    budget = (
        db.query(Budget)
        .filter(
            Budget.id == budget_id,
            Budget.user_id == current_user.id,
        )
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
        db.query(func.coalesce(func.sum(Transaction.amount), 0.0))
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
