from pydantic import BaseModel, ConfigDict
from typing import List, Dict
from datetime import date


class DailyTotal(BaseModel):
    date: str
    amount: float


class SummaryResponse(BaseModel):
    total_income: float
    total_expenses: float
    net_balance: float
    by_category: Dict[str, float]
    daily_totals: List[DailyTotal]


class ForecastResponse(BaseModel):
    target_date: date
    predicted_amount: float
    model_type: str

    model_config = ConfigDict(from_attributes=True)


class GenerateForecastRequest(BaseModel):
    days_to_forecast: int = 30
