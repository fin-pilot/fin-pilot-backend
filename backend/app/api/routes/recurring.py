from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from backend.app.db.database import get_db
from backend.app.db.models import User
from backend.app.schemas.recurring import (
    RecurringCreate,
    RecurringResponse,
    RecurringUpdate,
)
from backend.app.api.dependencies import get_current_user
from backend.app.services.recurring_service import RecurringService

router = APIRouter(prefix="/api/recurring", tags=["recurring"])


@router.get("/", response_model=List[RecurringResponse])
def get_recurring_transactions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = RecurringService(db)
    return service.list_recurring(current_user.id)


@router.post(
    "/", response_model=RecurringResponse, status_code=status.HTTP_201_CREATED
)
def create_recurring_transaction(
    sub_in: RecurringCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = RecurringService(db)
    return service.create_recurring(current_user.id, sub_in)


@router.get("/{recurring_id}", response_model=RecurringResponse)
def get_recurring_transaction(
    recurring_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = RecurringService(db)
    return service.get_recurring(current_user.id, recurring_id)


@router.put("/{recurring_id}", response_model=RecurringResponse)
def update_recurring_transaction(
    recurring_id: UUID,
    sub_in: RecurringUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = RecurringService(db)
    return service.update_recurring(current_user.id, recurring_id, sub_in)


@router.delete("/{recurring_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recurring_transaction(
    recurring_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = RecurringService(db)
    service.delete_recurring(current_user.id, recurring_id)
    return None


@router.post("/process-manual")
def trigger_processing(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = RecurringService(db)
    _ = current_user
    count = service.process_due()

    return {"message": "Обробку завершено успішно", "processed_count": count}
