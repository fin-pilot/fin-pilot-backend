from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.db.database import get_db
from app.db.models import Transaction, Account, User, TransactionType
from app.schemas.transaction import (
    TransactionCreate,
    TransactionResponse,
    TransactionUpdate,
    PredictCategoryRequest,
    PredictCategoryResponse,
)
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("/", response_model=List[TransactionResponse])
def get_transactions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
):
    return (
        db.query(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .filter(Account.user_id == current_user.id)
        .order_by(Transaction.transaction_date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.post(
    "/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED
)
def create_transaction(
    trans_in: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = (
        db.query(Account)
        .filter(
            Account.id == trans_in.account_id,
            Account.user_id == current_user.id,
        )
        .first()
    )
    if not account:
        raise HTTPException(
            status_code=404, detail="Account not found or access denied"
        )

    if trans_in.transaction_type == TransactionType.INCOME:
        account.balance += trans_in.amount

    elif trans_in.transaction_type == TransactionType.EXPENSE:
        account.balance -= trans_in.amount

    elif trans_in.transaction_type == TransactionType.TRANSFER:
        dest_account = (
            db.query(Account)
            .filter(
                Account.id == trans_in.destination_account_id,
                Account.user_id == current_user.id,
            )
            .first()
        )
        if not dest_account:
            raise HTTPException(
                status_code=404, detail="Destination account not found"
            )

        account.balance -= trans_in.amount
        dest_account.balance += trans_in.amount

    new_transaction = Transaction(**trans_in.model_dump())
    db.add(new_transaction)
    db.commit()
    db.refresh(new_transaction)
    return new_transaction


@router.get("/{trans_id}", response_model=TransactionResponse)
def get_transaction(
    trans_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    trans = (
        db.query(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .filter(Transaction.id == trans_id, Account.user_id == current_user.id)
        .first()
    )

    if not trans:
        raise HTTPException(
            status_code=404, detail="Transaction not found or access denied"
        )

    return trans


@router.put("/{trans_id}", response_model=TransactionResponse)
def update_transaction(
    trans_id: UUID,
    trans_in: TransactionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    trans = (
        db.query(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .filter(Transaction.id == trans_id, Account.user_id == current_user.id)
        .first()
    )

    if not trans:
        raise HTTPException(
            status_code=404, detail="Transaction not found or access denied"
        )

    if trans_in.amount is not None and trans_in.amount != trans.amount:
        amount_difference = trans_in.amount - trans.amount
        account = trans.account

        if trans.transaction_type == TransactionType.INCOME:
            account.balance += amount_difference

        elif trans.transaction_type == TransactionType.EXPENSE:
            account.balance -= amount_difference

        elif trans.transaction_type == TransactionType.TRANSFER:
            dest_account = trans.destination_account
            if not dest_account:
                raise HTTPException(
                    status_code=500,
                    detail="Destination account missing for transfer",
                )

            account.balance -= amount_difference
            dest_account.balance += amount_difference

    update_data = trans_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(trans, key, value)

    db.commit()
    db.refresh(trans)

    return trans


@router.delete("/{trans_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    trans_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    trans = (
        db.query(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .filter(Transaction.id == trans_id, Account.user_id == current_user.id)
        .first()
    )

    if not trans:
        raise HTTPException(status_code=404, detail="Transaction not found")

    account = trans.account
    if trans.transaction_type == TransactionType.INCOME:
        account.balance -= trans.amount
    elif trans.transaction_type == TransactionType.EXPENSE:
        account.balance += trans.amount
    elif trans.transaction_type == TransactionType.TRANSFER:
        dest_account = trans.destination_account
        account.balance += trans.amount
        if dest_account:
            dest_account.balance -= trans.amount

    db.delete(trans)
    db.commit()
    return None


@router.post("/predict-category", response_model=PredictCategoryResponse)
def predict_transaction_category(
    request: PredictCategoryRequest,
    current_user: User = Depends(get_current_user),
):
    description = request.description.lower()

    # TODO: Тут у майбутньому буде підключена ваша реальна NLP/ML модель
    # Поки що робимо Mock-відповідь для тестування фронтенду

    # Mock логіка:
    predicted_category = None
    confidence = 0.0
    message = "Model is not fully integrated yet. Returning mock data."

    if "сільпо" in description or "атб" in description:
        confidence = 0.89
        message = "Predicted as 'Groceries' based on keywords."

    return PredictCategoryResponse(
        predicted_category_id=predicted_category,
        confidence_score=confidence,
        message=message,
    )
