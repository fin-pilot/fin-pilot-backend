from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from datetime import date

from backend.app.db.database import get_db
from backend.app.db.models import RecurringTransaction, User
from backend.app.schemas.recurring import (
    RecurringCreate,
    RecurringResponse,
    RecurringUpdate,
)
from backend.app.api.dependencies import get_current_user
from backend.app.services.recurring_service import (
    process_recurring_transactions,
)

router = APIRouter(prefix="/api/recurring", tags=["recurring"])


@router.get("/", response_model=List[RecurringResponse])
def get_recurring_transactions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(RecurringTransaction)
        .filter(RecurringTransaction.user_id == current_user.id)
        .all()
    )


@router.post(
    "/", response_model=RecurringResponse, status_code=status.HTTP_201_CREATED
)
def create_recurring_transaction(
    sub_in: RecurringCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    next_run = sub_in.start_date or date.today()

    new_sub = RecurringTransaction(
        **sub_in.model_dump(), user_id=current_user.id, next_date=next_run
    )

    db.add(new_sub)
    db.commit()
    db.refresh(new_sub)
    return new_sub


@router.get("/{recurring_id}", response_model=RecurringResponse)
def get_recurring_transaction(
    recurring_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sub = (
        db.query(RecurringTransaction)
        .filter(
            RecurringTransaction.id == recurring_id,
            RecurringTransaction.user_id == current_user.id,
        )
        .first()
    )

    if not sub:
        raise HTTPException(
            status_code=404, detail="Регулярний платіж не знайдено"
        )

    return sub


@router.put("/{recurring_id}", response_model=RecurringResponse)
def update_recurring_transaction(
    recurring_id: UUID,
    sub_in: RecurringUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sub = (
        db.query(RecurringTransaction)
        .filter(
            RecurringTransaction.id == recurring_id,
            RecurringTransaction.user_id == current_user.id,
        )
        .first()
    )

    if not sub:
        raise HTTPException(
            status_code=404, detail="Регулярний платіж не знайдено"
        )

    update_data = sub_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(sub, key, value)

    db.commit()
    db.refresh(sub)
    return sub


@router.delete("/{recurring_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recurring_transaction(
    recurring_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sub = (
        db.query(RecurringTransaction)
        .filter(
            RecurringTransaction.id == recurring_id,
            RecurringTransaction.user_id == current_user.id,
        )
        .first()
    )

    if not sub:
        raise HTTPException(
            status_code=404, detail="Регулярний платіж не знайдено"
        )

    db.delete(sub)
    db.commit()
    return None


@router.post("/process-manual")
def trigger_processing(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = process_recurring_transactions(db)

    return {"message": "Обробку завершено успішно", "processed_count": count}
