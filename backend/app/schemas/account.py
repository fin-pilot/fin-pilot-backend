from pydantic import BaseModel, ConfigDict
from typing import Optional
import uuid
from app.db.models import AccountType


class AccountBase(BaseModel):
    name: str
    account_type: AccountType = AccountType.CARD
    balance: float = 0.0
    currency: str = "UAH"


class AccountCreate(AccountBase):
    pass


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    account_type: Optional[AccountType] = None
    balance: Optional[float] = None
    currency: Optional[str] = None


class AccountResponse(AccountBase):
    id: uuid.UUID
    user_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)
