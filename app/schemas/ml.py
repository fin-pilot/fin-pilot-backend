from typing import Optional, List, Dict
from pydantic import UUID4, BaseModel
from datetime import date


class PredictCategoryRequest(BaseModel):
    description: str


class PredictCategoryResponse(BaseModel):
    predicted_category_id: Optional[UUID4]
    predicted_label: Optional[str] = None
    message: str
    is_fallback: bool = False


class ForecastPoint(BaseModel):
    date: date
    predicted_amount: float


class PredictForecastResponse(BaseModel):
    predictions: List[ForecastPoint]
    message: str


class SeasonalityResponse(BaseModel):
    user_id: UUID4
    seasonal_patterns: Dict[str, float]
    message: str
