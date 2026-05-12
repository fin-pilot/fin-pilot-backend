from typing import Optional

from pydantic import UUID4, BaseModel


class PredictCategoryRequest(BaseModel):
    description: str


class PredictCategoryResponse(BaseModel):
    predicted_category_id: Optional[UUID4]
    predicted_label: Optional[str] = None
    confidence_score: float
    message: str
