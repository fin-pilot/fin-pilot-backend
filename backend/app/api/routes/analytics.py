from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional, Literal

import pandas as pd
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import (
    Account,
    Budget,
    Forecast,
    Transaction,
    TransactionType,
    User,
)
from app.schemas.analytics import (
    AnomalyItem,
    BudgetUtilization,
    CashflowData,
    CategorySpending,
    ForecastResponse,
    RecommendationsResponse,
    SummaryResponse,
)
from app.services.recommender import FinanceRecommender

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _range_filters(start: Optional[date], end: Optional[date]):
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
        .join(Account)
        .filter(Account.user_id == current_user.id)
    )
    for f in _range_filters(start_date, end_date):
        base = base.filter(f)

    transactions = base.all()

    income, expense = 0.0, 0.0
    by_cat, daily_totals_map = {}, {}

    for t in transactions:
        if t.type == TransactionType.INCOME:
            income += t.amount
        elif t.type == TransactionType.EXPENSE:
            expense += t.amount
            if t.category:
                by_cat[t.category.name] = (
                    by_cat.get(t.category.name, 0.0) + t.amount
                )

        date_str = t.transaction_date.date().isoformat()
        daily_totals_map.setdefault(date_str, 0.0)
        daily_totals_map[date_str] += (
            t.amount if t.type == TransactionType.INCOME else -t.amount
        )

    daily_totals_list = [
        {"date": d, "amount": a} for d, a in sorted(daily_totals_map.items())
    ]

    return {
        "total_income": income,
        "total_expenses": expense,
        "net_balance": income - expense,
        "by_category": by_cat,
        "daily_totals": daily_totals_list,
    }


@router.get("/spending-by-category", response_model=List[CategorySpending])
def get_spending_by_category(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    transaction_type: str = Query("expense"),
):
    base = (
        db.query(Transaction)
        .join(Account)
        .filter(
            Account.user_id == current_user.id,
            Transaction.type == transaction_type,
        )
    )
    for f in _range_filters(start_date, end_date):
        base = base.filter(f)

    cat_totals = {}
    total_amount = 0.0

    for t in base.all():
        cat_name = t.category.name if t.category else "Інше"
        cat_totals[cat_name] = cat_totals.get(cat_name, 0.0) + t.amount
        total_amount += t.amount

    result = [
        CategorySpending(
            category_name=name,
            amount=round(amount, 2),
            percentage=(
                round((amount / total_amount * 100), 2)
                if total_amount > 0
                else 0.0
            ),
        )
        for name, amount in cat_totals.items()
    ]
    result.sort(key=lambda x: x.amount, reverse=True)
    return result


@router.get("/cashflow", response_model=List[CashflowData])
def get_cashflow(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    interval: Literal["daily", "weekly", "monthly"] = Query("daily"),
):
    base = (
        db.query(Transaction)
        .join(Account)
        .filter(Account.user_id == current_user.id)
    )
    for f in _range_filters(start_date, end_date):
        base = base.filter(f)

    transactions = base.all()
    if not transactions:
        return []

    data = []
    for t in transactions:
        inc = t.amount if t.type == TransactionType.INCOME else 0.0
        exp = t.amount if t.type == TransactionType.EXPENSE else 0.0
        data.append({"date": t.transaction_date, "income": inc, "expense": exp})

    df = pd.DataFrame(data)
    df.set_index("date", inplace=True)

    if interval == "weekly":
        df = df.resample("W").sum()
    elif interval == "monthly":
        df = df.resample("ME").sum()
    else:
        df = df.resample("D").sum()

    df = df.fillna(0).reset_index()

    return [
        CashflowData(
            date=row["date"].strftime("%Y-%m-%d"),
            income=round(row["income"], 2),
            expense=round(row["expense"], 2),
        )
        for _, row in df.iterrows()
    ]


@router.get("/budget-utilization", response_model=List[BudgetUtilization])
def get_budget_utilization(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    budgets = db.query(Budget).filter(Budget.user_id == current_user.id).all()
    result = []

    for b in budgets:
        spent = getattr(b, "spent_amount", 0.0)
        pct = (spent / b.amount * 100) if b.amount > 0 else 0.0
        status = (
            "green" if pct < 75.0 else ("yellow" if pct <= 100.0 else "red")
        )

        result.append(
            BudgetUtilization(
                budget_id=b.id,
                budget_name=b.name,
                amount_limit=b.amount,
                spent_amount=spent,
                percentage=round(pct, 2),
                status=status,
            )
        )
    return result


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


@router.get("/anomalies", response_model=List[AnomalyItem])
def get_anomalies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    window_days: int = Query(30, ge=7, le=365),
):
    start_date = date.today() - timedelta(days=window_days)
    transactions = (
        db.query(Transaction)
        .join(Account)
        .filter(
            Account.user_id == current_user.id,
            Transaction.type == TransactionType.EXPENSE,
            Transaction.transaction_date
            >= datetime.combine(start_date, time.min, tzinfo=timezone.utc),
        )
        .all()
    )

    if len(transactions) < 5:
        return []

    amounts = [t.amount for t in transactions]
    mean_amt = sum(amounts) / len(amounts)
    std_dev = math.sqrt(
        sum((x - mean_amt) ** 2 for x in amounts) / len(amounts)
    )

    anomalies = []
    for t in transactions:
        if std_dev < 1:
            continue
        if t.amount > mean_amt + (3 * std_dev):
            lvl = "high"
        elif t.amount > mean_amt + (2 * std_dev):
            lvl = "medium"
        else:
            continue

        anomalies.append(
            AnomalyItem(
                transaction_id=t.id,
                date=t.transaction_date.date().isoformat(),
                description=t.description or "Невідома",
                amount=round(t.amount, 2),
                anomaly_level=lvl,
            )
        )
    anomalies.sort(key=lambda x: x.amount, reverse=True)
    return anomalies


@router.get("/recommendations", response_model=RecommendationsResponse)
def get_recommendations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rec_engine = FinanceRecommender()

    start_date = date.today() - timedelta(days=30)
    txs = (
        db.query(Transaction)
        .join(Account)
        .filter(
            Account.user_id == current_user.id,
            Transaction.transaction_date
            >= datetime.combine(start_date, time.min, tzinfo=timezone.utc),
        )
        .all()
    )

    inc = sum(t.amount for t in txs if t.type == TransactionType.INCOME)
    exp_by_cat = {}
    for t in txs:
        if t.type == TransactionType.EXPENSE and t.category:
            exp_by_cat[t.category.name] = (
                exp_by_cat.get(t.category.name, 0.0) + t.amount
            )

    tips = rec_engine.analyze_spending(inc, exp_by_cat)
    return {"recommendations": tips}
