from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import (
    Account,
    Forecast,
    Transaction,
    TransactionType,
    User,
)
from ml.recommender import FinanceRecommender
from app.schemas.analytics import (
    ForecastResponse,
    GenerateForecastRequest,
    OverspendingPoint,
    RecommendationsResponse,
    SummaryResponse,
)
from app.services.expense_series import daily_expense_dataframe
from app.services.user_forecaster import train_forecaster_for_history

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _range_filters(
    start: Optional[date],
    end: Optional[date],
):
    flt = []
    if start is not None:
        flt.append(
            Transaction.transaction_date
            >= datetime.combine(start, time.min, tzinfo=timezone.utc)
        )
    if end is not None:
        flt.append(
            Transaction.transaction_date
            <= datetime.combine(end, time.max, tzinfo=timezone.utc)
        )
    return flt


@router.get("/summary", response_model=SummaryResponse)
def get_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
):
    base = (
        db.query(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .filter(Account.user_id == current_user.id)
    )
    for f in _range_filters(start_date, end_date):
        base = base.filter(f)

    transactions = base.all()

    income = 0.0
    expense = 0.0
    by_cat: dict[str, float] = {}
    daily_totals_map: dict[str, float] = {}

    for t in transactions:
        if t.transaction_type == TransactionType.INCOME:
            income += t.amount
        elif t.transaction_type == TransactionType.EXPENSE:
            expense += t.amount

        if t.transaction_type == TransactionType.EXPENSE and t.category:
            name = t.category.name
            by_cat[name] = by_cat.get(name, 0.0) + t.amount

        date_str = t.transaction_date.date().isoformat()
        daily_totals_map.setdefault(date_str, 0.0)
        if t.transaction_type == TransactionType.INCOME:
            daily_totals_map[date_str] += t.amount
        elif t.transaction_type == TransactionType.EXPENSE:
            daily_totals_map[date_str] -= t.amount

    daily_totals_list = [
        {"date": d_str, "amount": amt}
        for d_str, amt in sorted(daily_totals_map.items())
    ]

    return {
        "total_income": income,
        "total_expenses": expense,
        "net_balance": income - expense,
        "by_category": by_cat,
        "daily_totals": daily_totals_list,
    }


@router.post("/forecast/generate", status_code=201)
def generate_forecast(
    req: GenerateForecastRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    df = daily_expense_dataframe(db, current_user.id)
    try:
        forecaster = train_forecaster_for_history(df)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = forecaster.forecast(steps=req.days_to_forecast)
    last_ts = pd.Timestamp(forecaster.series.index[-1])
    dates = [
        last_ts + pd.Timedelta(days=i + 1) for i in range(req.days_to_forecast)
    ]

    db.query(Forecast).filter(Forecast.user_id == current_user.id).delete()

    n = min(len(dates), len(result.predictions))
    for i in range(n):
        dt = dates[i]
        amt = result.predictions[i]
        val = max(0.0, float(amt))
        ts = pd.Timestamp(dt).to_pydatetime()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        row = Forecast(
            user_id=current_user.id,
            target_date=ts,
            predicted_amount=val,
            model_type="SARIMA",
        )
        db.add(row)

    db.commit()
    return {
        "message": (
            f"Forecast for {req.days_to_forecast} days generated successfully."
        )
    }


@router.get("/forecast", response_model=List[ForecastResponse])
def list_forecast(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(Forecast)
        .filter(Forecast.user_id == current_user.id)
        .order_by(Forecast.target_date)
        .all()
    )
    return [ForecastResponse.from_forecast_row(r) for r in rows]


@router.get("/recommendations", response_model=RecommendationsResponse)
def get_recommendations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
):
    base = (
        db.query(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .filter(Account.user_id == current_user.id)
    )
    for f in _range_filters(start_date, end_date):
        base = base.filter(f)

    income = 0.0
    expenses_by_category: dict[str, float] = {}

    for t in base.all():
        if t.transaction_type == TransactionType.INCOME:
            income += t.amount
        elif t.transaction_type == TransactionType.EXPENSE and t.category:
            name = t.category.name
            expenses_by_category[name] = (
                expenses_by_category.get(name, 0.0) + t.amount
            )

    rec = FinanceRecommender()
    tips = rec.analyze_spending(income, expenses_by_category)
    return {"recommendations": tips}


@router.get("/overspending", response_model=List[OverspendingPoint])
def get_overspending(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    window: int = Query(30, ge=3, le=365),
    threshold: float = Query(2.0, ge=0.5, le=10.0),
):
    df = daily_expense_dataframe(db, current_user.id)
    if len(df) < 7:
        raise HTTPException(
            status_code=400,
            detail="Need at least 7 days of expense history.",
        )
    try:
        forecaster = train_forecaster_for_history(df)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    anomalies = forecaster.detect_overspending(
        df,
        date_col="date",
        amount_col="amount",
        window=window,
        threshold=threshold,
    )
    out: List[OverspendingPoint] = []
    for idx, val in anomalies.items():
        out.append(
            OverspendingPoint(
                date=pd.Timestamp(idx).date().isoformat(),
                amount=float(val),
            )
        )
    return out
