from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
import pandas as pd
from typing import List

from app.db.database import get_db
from app.db.models import Transaction, Forecast, Account, User, TransactionType
from app.schemas.analytics import (
    SummaryResponse,
    ForecastResponse,
    GenerateForecastRequest,
)
from app.api.deps import get_current_user
from app.ml.forecasting import run_sarima_forecast

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/summary", response_model=SummaryResponse)
def get_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        db.query(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .filter(Account.user_id == current_user.id)
    )
    transactions = query.all()

    income = 0.0
    expense = 0.0
    by_cat = {}
    daily_totals_map = {}

    for t in transactions:
        if t.transaction_type == TransactionType.INCOME:
            income += t.amount
        elif t.transaction_type == TransactionType.EXPENSE:
            expense += t.amount

        if t.category:
            name = t.category.name
            by_cat[name] = by_cat.get(name, 0) + t.amount

        date_str = t.transaction_date.date().isoformat()

        if date_str not in daily_totals_map:
            daily_totals_map[date_str] = 0.0

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
    history_data = (
        db.query(
            func.date(Transaction.transaction_date).label("ds"),
            func.sum(Transaction.amount).label("y"),
        )
        .join(Account, Transaction.account_id == Account.id)
        .filter(
            Account.user_id == current_user.id,
            Transaction.transaction_type == TransactionType.EXPENSE,
        )
        .group_by(func.date(Transaction.transaction_date))
        .all()
    )

    if len(history_data) < 7:
        raise HTTPException(
            status_code=400,
            detail="Need at least 7 days of history for forecasting",
        )

    df = pd.DataFrame(history_data)

    predictions = run_sarima_forecast(df, steps=req.days_to_forecast)

    db.query(Forecast).filter(Forecast.user_id == current_user.id).delete()

    for p in predictions:
        new_f = Forecast(
            user_id=current_user.id,
            target_date=p["date"],
            predicted_amount=p["amount"],
            model_type="SARIMA",
        )
        db.add(new_f)

    db.commit()
    return {
        "message": f"Forecast for {req.days_to_forecast} days generated successfully"
    }


@router.get("/forecast", response_model=List[ForecastResponse])
def get_forecast(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Forecast)
        .filter(Forecast.user_id == current_user.id)
        .order_by(Forecast.target_date)
        .all()
    )
