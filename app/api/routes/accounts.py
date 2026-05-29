from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.db.database import get_db
from app.db.models import User
from app.schemas.account import (
    AccountCreate,
    AccountResponse,
    AccountUpdate,
)
from app.api.dependencies import get_current_user
from app.services.account_service import AccountService

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("/", response_model=List[AccountResponse])
def get_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AccountService(db)
    return service.list_accounts(current_user.id)


@router.post(
    "/", response_model=AccountResponse, status_code=status.HTTP_201_CREATED
)
def create_account(
    account_in: AccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AccountService(db)
    return service.create_account(current_user.id, account_in)


@router.get("/{account_id}", response_model=AccountResponse)
def get_account(
    account_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AccountService(db)
    return service.get_account(current_user.id, account_id)


@router.put("/{account_id}", response_model=AccountResponse)
def update_account(
    account_id: uuid.UUID,
    account_in: AccountUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AccountService(db)
    return service.update_account(current_user.id, account_id, account_in)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    account_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AccountService(db)
    service.delete_account(current_user.id, account_id)
    return None
