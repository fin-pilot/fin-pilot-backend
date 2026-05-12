from datetime import date, datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


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

    @classmethod
    def from_forecast_row(cls, row) -> "ForecastResponse":
        td = row.target_date
        if isinstance(td, datetime):
            td = td.date()
        return cls(
            target_date=td,
            predicted_amount=float(row.predicted_amount),
            model_type=row.model_type or "SARIMA",
        )


class GenerateForecastRequest(BaseModel):
    days_to_forecast: int = Field(default=30, ge=1, le=365)


class OverspendingPoint(BaseModel):
    date: str
    amount: float


class RecommendationsResponse(BaseModel):
    recommendations: List[str]


class ImportSummaryResponse(BaseModel):
    created: int
    skipped: int
    errors: List[str]
