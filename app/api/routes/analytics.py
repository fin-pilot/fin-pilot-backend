from __future__ import annotations

from datetime import date
from typing import List, Optional, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import User
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
    service = _service(db)
    return service.summary(current_user.id, start_date, end_date)


@router.get("/spending-by-category", response_model=List[CategorySpending])
def get_spending_by_category(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    transaction_type: str = Query("expense"),
):
    service = _service(db)
    return service.spending_by_category(
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
    service = _service(db)
    return service.cashflow(current_user.id, start_date, end_date, interval)


@router.get("/budget-utilization", response_model=List[BudgetUtilization])
def get_budget_utilization(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = _service(db)
    return service.budget_utilization(current_user.id)


@router.get("/forecast", response_model=List[ForecastResponse])
def list_forecast(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = _service(db)
    return service.list_forecast(current_user.id)


@router.get("/anomalies", response_model=List[AnomalyItem])
def get_anomalies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    window_days: int = Query(30, ge=7, le=365),
):
    service = _service(db)
    return service.anomalies(current_user.id, window_days)


@router.get("/recommendations", response_model=RecommendationsResponse)
def get_recommendations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = _service(db)
    return {"recommendations": service.recommendations(current_user.id)}
