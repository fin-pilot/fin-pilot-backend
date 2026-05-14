from __future__ import annotations

from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_current_user
from backend.app.db.database import get_db
from backend.app.db.models import User
from backend.app.schemas.transaction import (
    TransactionCreate,
    TransactionImportResult,
    TransactionResponse,
    TransactionUpdate,
)
from backend.app.services.transaction_service import TransactionService

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("/", response_model=List[TransactionResponse])
def get_transactions(
    skip: int = Query(0, ge=0, description="Скільки записів пропустити"),
    limit: int = Query(
        100, ge=1, le=1000, description="Максимальна кількість записів"
    ),
    start_date: Optional[date] = Query(
        None, description="Початкова дата (формат YYYY-MM-DD)"
    ),
    end_date: Optional[date] = Query(
        None, description="Кінцева дата (формат YYYY-MM-DD)"
    ),
    account_id: Optional[UUID] = Query(
        None, description="Фільтр за ID рахунку"
    ),
    category_id: Optional[UUID] = Query(
        None, description="Фільтр за ID категорії"
    ),
    transaction_type: Optional[str] = Query(
        None,
        description=(
            "Тип транзакції (наприклад: 'expense', 'income', 'transfer')"
        ),
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = TransactionService(db)
    return service.list_transactions(
        current_user.id,
        skip=skip,
        limit=limit,
        start_date=start_date,
        end_date=end_date,
        account_id=account_id,
        category_id=category_id,
        transaction_type=transaction_type,
    )


@router.post(
    "/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED
)
def create_transaction(
    trans_in: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = TransactionService(db)
    return service.create_transaction(current_user.id, trans_in)


@router.get("/export")
def export_transactions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = TransactionService(db)
    return StreamingResponse(
        service.export_transactions(current_user.id),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=transactions.csv",
        },
    )


@router.post("/import", response_model=TransactionImportResult)
async def import_transactions_csv(
    file: UploadFile = File(...),
    default_account_id: UUID = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    raw = await file.read()
    service = TransactionService(db)
    return service.import_transactions(
        current_user.id,
        file_bytes=raw,
        default_account_id=default_account_id,
    )


@router.get("/{trans_id}", response_model=TransactionResponse)
def get_transaction(
    trans_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = TransactionService(db)
    return service.get_transaction(current_user.id, trans_id)


@router.put("/{trans_id}", response_model=TransactionResponse)
def update_transaction(
    trans_id: UUID,
    trans_in: TransactionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = TransactionService(db)
    return service.update_transaction(current_user.id, trans_id, trans_in)


@router.delete("/{trans_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    trans_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = TransactionService(db)
    service.delete_transaction(current_user.id, trans_id)
    return None
