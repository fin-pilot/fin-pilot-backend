from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime
from uuid import UUID


class GoalBase(BaseModel):
    name: str = Field(
        ..., min_length=1, max_length=100, description="Назва цілі"
    )
    target_amount: float = Field(
        ..., gt=0, description="Сума, яку потрібно зібрати"
    )
    deadline: Optional[date] = Field(None, description="Кінцева дата (дедлайн)")


class GoalCreate(GoalBase):
    current_amount: Optional[float] = Field(0.0, ge=0)


class GoalUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    target_amount: Optional[float] = Field(None, gt=0)
    deadline: Optional[date] = None


class GoalContribute(BaseModel):
    amount: float = Field(
        ..., gt=0, description="Сума, яку ви хочете додати до цілі"
    )


class GoalResponse(GoalBase):
    id: UUID
    user_id: UUID
    current_amount: float
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
