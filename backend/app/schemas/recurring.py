from pydantic import BaseModel, Field
from typing import Optional
from datetime import date
from uuid import UUID
from app.db.models import RecurringInterval


class RecurringBase(BaseModel):
    description: str
    amount: float = Field(..., gt=0)
    account_id: UUID
    category_id: Optional[UUID] = None
    type: str = "expense"
    interval: RecurringInterval
    start_date: Optional[date] = None


class RecurringCreate(RecurringBase):
    pass


class RecurringUpdate(BaseModel):
    description: Optional[str] = None
    amount: Optional[float] = None
    is_active: Optional[bool] = None
    next_date: Optional[date] = None


class RecurringResponse(RecurringBase):
    id: UUID
    user_id: UUID
    next_date: date
    is_active: bool

    class Config:
        from_attributes = True
