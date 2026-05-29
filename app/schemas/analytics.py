from datetime import date, datetime
from typing import Dict, List, Optional
from uuid import UUID

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


class CategorySpending(BaseModel):
    category_name: str = Field(description="Назва категорії")
    amount: float = Field(description="Загальна сума витрат у цій категорії")
    percentage: float = Field(
        description="Відсоток від загальних витрат (0-100)"
    )


class CashflowData(BaseModel):
    date: str = Field(description="Дата або початок періоду (тижня/місяця)")
    income: float = Field(description="Сума доходів за період")
    expense: float = Field(description="Сума витрат за період")


class BudgetUtilization(BaseModel):
    budget_id: UUID
    budget_name: str
    amount_limit: float = Field(description="Ліміт бюджету")
    spent_amount: float = Field(description="Скільки вже витрачено")
    percentage: float = Field(description="Відсоток використання")
    status: str = Field(description="Статус: 'green', 'yellow' або 'red'")


class AnomalyItem(BaseModel):
    transaction_id: Optional[UUID] = None
    date: str
    description: str = Field(description="Опис транзакції")
    amount: float
    anomaly_level: str = Field(
        description="Рівень аномальності: 'high' (вище 3 сигм) або 'medium' (вище 2 сигм)"
    )


class RecommendationItem(BaseModel):
    text: str = Field(description="Текст персоналізованої поради")
    type: str = Field(description="Тип: 'warning', 'success' або 'info'")
    action_link: Optional[str] = Field(
        None,
        description="Посилання для швидкої дії на фронтенді (наприклад, '/budgets')",
    )
