from pydantic import BaseModel, ConfigDict, UUID4, Field, model_validator
from typing import List, Optional
from datetime import datetime
from backend.app.db.models import TransactionType


class TransactionBase(BaseModel):
    account_id: UUID4
    category_id: UUID4
    destination_account_id: Optional[UUID4] = None
    amount: float
    description: Optional[str] = None
    transaction_type: TransactionType
    transaction_date: datetime = Field(
        default_factory=lambda: datetime.now().astimezone()
    )


class TransactionCreate(TransactionBase):
    @model_validator(mode="after")
    def check_transfer_logic(self):
        if (
            self.transaction_type == TransactionType.TRANSFER
            and not self.destination_account_id
        ):
            raise ValueError(
                "Destination account is required for TRANSFER type"
            )
        if (
            self.transaction_type != TransactionType.TRANSFER
            and self.destination_account_id
        ):
            raise ValueError(
                "Destination account should only be used for TRANSFER type"
            )
        return self


class TransactionUpdate(BaseModel):
    category_id: Optional[UUID4] = None
    amount: Optional[float] = None
    description: Optional[str] = None
    transaction_date: Optional[datetime] = None


class TransactionResponse(TransactionBase):
    id: UUID4

    model_config = ConfigDict(from_attributes=True)


class TransactionImportResult(BaseModel):
    created: int
    skipped: int
    errors: List[str]
