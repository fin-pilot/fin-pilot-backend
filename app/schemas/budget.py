from pydantic import BaseModel, ConfigDict, UUID4
from typing import Optional
from datetime import datetime


class BudgetBase(BaseModel):
    category_id: UUID4
    limit_amount: float
    start_date: datetime
    end_date: datetime


class BudgetCreate(BudgetBase):
    name: Optional[str] = None


class BudgetUpdate(BaseModel):
    name: Optional[str] = None
    limit_amount: Optional[float] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class BudgetResponse(BudgetBase):
    id: UUID4
    user_id: Optional[UUID4]
    name: str
    spent_amount: float = 0.0
    is_default: bool = False

    model_config = ConfigDict(from_attributes=True)
