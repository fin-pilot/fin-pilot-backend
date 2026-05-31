from __future__ import annotations

from datetime import date
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.i18n import get_locale
from app.schemas.analytics import (
    AnomalyItem,
    BudgetUtilization,
    CashflowData,
    CategorySpending,
    ForecastResponse,
    RecommendationsResponse,
    SummaryResponse,
)
from app.services.analytic_service import AnalyticsService

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _service(db: Session) -> AnalyticsService:
    return AnalyticsService(db)


@router.get("/summary", response_model=SummaryResponse)
def get_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
):
    return _service(db).summary(current_user.id, start_date, end_date)


@router.get("/spending-by-category", response_model=List[CategorySpending])
def get_spending_by_category(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    transaction_type: str = Query("expense"),
):
    return _service(db).spending_by_category(
        current_user.id, start_date, end_date, transaction_type
    )


@router.get("/cashflow", response_model=List[CashflowData])
def get_cashflow(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    interval: Literal["daily", "weekly", "monthly"] = Query("daily"),
):
    return _service(db).cashflow(current_user.id, start_date, end_date, interval)


@router.get("/budget-utilization", response_model=List[BudgetUtilization])
def get_budget_utilization(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _service(db).budget_utilization(current_user.id)


@router.get("/forecast", response_model=List[ForecastResponse])
def list_forecast(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return stored weekly forecasts (written after each training run)."""
    return _service(db).list_forecast(current_user.id)


@router.get("/anomalies", response_model=List[AnomalyItem])
def get_anomalies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    window_days: int = Query(30, ge=7, le=365),
):
    return _service(db).anomalies(current_user.id, window_days)


@router.get("/recommendations", response_model=RecommendationsResponse)
def get_recommendations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Return three-tier ML-powered financial recommendations."""
    return _service(db).recommendations(current_user.id, locale=locale)
