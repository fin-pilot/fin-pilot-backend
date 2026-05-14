from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from uuid import UUID

from backend.app.db.database import get_db
from backend.app.db.models import User
from backend.app.schemas.budget import (
    BudgetCreate,
    BudgetResponse,
    BudgetUpdate,
)
from backend.app.api.dependencies import get_current_user
from backend.app.services.budget_service import BudgetService

router = APIRouter(prefix="/api/budgets", tags=["budgets"])


@router.get("/", response_model=list[BudgetResponse])
def get_budgets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = BudgetService(db)
    return service.list_budgets(current_user.id)


@router.post(
    "/", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED
)
def create_budget(
    budget_in: BudgetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = BudgetService(db)
    return service.create_budget(current_user.id, budget_in)


@router.put("/{budget_id}", response_model=BudgetResponse)
def update_budget(
    budget_id: UUID,
    budget_in: BudgetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = BudgetService(db)
    return service.update_budget(current_user.id, budget_id, budget_in)


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(
    budget_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = BudgetService(db)
    service.delete_budget(current_user.id, budget_id)
    return None
