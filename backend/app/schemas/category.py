from pydantic import BaseModel, ConfigDict, UUID4
from typing import Optional
from backend.app.db.models import TransactionType


class CategoryBase(BaseModel):
    name: str
    type: TransactionType


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[TransactionType] = None


class CategoryResponse(CategoryBase):
    id: UUID4
    user_id: Optional[UUID4] = None

    model_config = ConfigDict(from_attributes=True)
