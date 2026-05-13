from pydantic import BaseModel, ConfigDict, UUID4
from typing import Optional
from backend.app.db.models import AccountType


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
    id: UUID4
    user_id: UUID4

    model_config = ConfigDict(from_attributes=True)
