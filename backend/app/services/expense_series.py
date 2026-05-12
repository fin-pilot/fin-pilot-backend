"""Build per-user daily expense aggregates for forecasting and anomaly checks."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Optional
from uuid import UUID

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import Account, Transaction, TransactionType


def daily_expense_dataframe(
    db: Session,
    user_id: UUID,
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> pd.DataFrame:
    q = (
        db.query(
            func.date(Transaction.transaction_date).label("date"),
            func.sum(Transaction.amount).label("amount"),
        )
        .join(Account, Transaction.account_id == Account.id)
        .filter(
            Account.user_id == user_id,
            Transaction.transaction_type == TransactionType.EXPENSE,
        )
    )
    if start is not None:
        q = q.filter(
            Transaction.transaction_date
            >= datetime.combine(start, time.min, tzinfo=timezone.utc)
        )
    if end is not None:
        q = q.filter(
            Transaction.transaction_date
            <= datetime.combine(end, time.max, tzinfo=timezone.utc)
        )
    rows = q.group_by(func.date(Transaction.transaction_date)).all()
    if not rows:
        return pd.DataFrame(columns=["date", "amount"])
    df = pd.DataFrame([{"date": r.date, "amount": float(r.amount or 0)} for r in rows])
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date")
