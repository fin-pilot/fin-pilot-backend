"""Pydantic schemas for the /api/ml routes.

Designed to mirror fin_pilot_ml.schemas outputs so the route layer only
needs to pass responses through without transformation.
"""

from __future__ import annotations

from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Categorisation ────────────────────────────────────────────────────────────

class PredictCategoryRequest(BaseModel):
    description: str = Field(description="Текстовий опис транзакції")


class PredictCategoryResponse(BaseModel):
    predicted_category_id: Optional[UUID] = None
    predicted_label: Optional[str] = None
    confidence: float = Field(0.0, description="Confidence score від моделі (0.0–1.0)")
    message: str
    is_fallback: bool = False


# ── Forecasting ───────────────────────────────────────────────────────────────

class WeeklyForecastPoint(BaseModel):
    week_start: str = Field(description="ISO date string — початок тижня")
    predicted_expense: float = Field(description="Прогнозована сума витрат за тиждень")


class ForecastStatusResponse(BaseModel):
    is_cold_start: bool = Field(
        description="True якщо модель ще не навчена або даних недостатньо"
    )
    model_used: str = Field(description='"sarima" або "none"')
    weeks: list[WeeklyForecastPoint]
    generated_at: str = Field(description="UTC ISO-8601 timestamp генерації")


# ── Recommendations (three-tier) ──────────────────────────────────────────────

class RecommendationItemV2(BaseModel):
    tier: Literal["preventive", "optimisation", "strategic"] = Field(
        description="Рівень рекомендації"
    )
    category: str = Field(description="Категорія витрат, якої стосується порада")
    diagnosis: str = Field(description="Діагностика виявленої ситуації")
    action: str = Field(description="Конкретна пропозиція дії з числовим параметром")
    projected_effect: str = Field(description="Прогнозований ефект від виконання")
    confidence: float = Field(description="Впевненість алгоритму (0.0–1.0)")


class RecommendationsResponseV2(BaseModel):
    recommendations: list[RecommendationItemV2]
    generated_at: str


# ── ML status ─────────────────────────────────────────────────────────────────

class MLStatusResponse(BaseModel):
    categoriser_loaded: bool
    sarima_loaded: bool
    training_status: Optional[str] = Field(
        None,
        description="Статус навчання: pending | training | ready | failed",
    )
    last_trained_at: Optional[str] = Field(
        None, description="UTC ISO-8601 timestamp останнього навчання"
    )
    n_training_samples: Optional[int] = Field(
        None, description="Кількість транзакцій, використаних при навчанні"
    )
    error_message: Optional[str] = None


# ── Academic metrics ──────────────────────────────────────────────────────────

class ModelMetricsResponse(BaseModel):
    categoriser: Optional[dict] = Field(
        None,
        description="Метрики класифікатора (F1, Precision, Recall, MCC) з artifacts/",
    )
    forecasting: Optional[dict] = Field(
        None,
        description="Метрики прогнозування (MAE, RMSE, WAPE, SMAPE) з artifacts/",
    )
