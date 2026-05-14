from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Literal
from uuid import UUID

from sqlalchemy import case, func
from sqlalchemy.sql import functions
from sqlalchemy.orm import Session

from backend.app.db.models import (
    Account,
    Budget,
    Category,
    Transaction,
    TransactionType,
)


class AnalyticsRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def _range_filters(self, start: date | None, end: date | None) -> list:
        filters = []
        if start is not None:
            filters.append(
                Transaction.transaction_date
                >= datetime.combine(start, time.min, tzinfo=timezone.utc)
            )
        if end is not None:
            filters.append(
                Transaction.transaction_date
                <= datetime.combine(end, time.max, tzinfo=timezone.utc)
            )
        return filters

    def summary_totals(
        self,
        user_id: UUID,
        start_date: date | None,
        end_date: date | None,
    ) -> tuple[float, float]:
        income_expr = case(
            (
                Transaction.transaction_type == TransactionType.INCOME,
                Transaction.amount,
            ),
            else_=0.0,
        )
        expense_expr = case(
            (
                Transaction.transaction_type == TransactionType.EXPENSE,
                Transaction.amount,
            ),
            else_=0.0,
        )
        query = (
            self._db.query(
                functions.coalesce(functions.sum(income_expr), 0.0),
                functions.coalesce(functions.sum(expense_expr), 0.0),
            )
            .join(Account, Transaction.account_id == Account.id)
            .filter(Account.user_id == user_id)
        )
        for flt in self._range_filters(start_date, end_date):
            query = query.filter(flt)
        income, expense = query.one()
        return float(income or 0), float(expense or 0)

    def summary_by_category(
        self,
        user_id: UUID,
        start_date: date | None,
        end_date: date | None,
    ) -> list[tuple[str, float]]:
        name_expr = functions.coalesce(Category.name, "Інше")
        query = (
            self._db.query(
                name_expr.label("category_name"),
                functions.coalesce(
                    functions.sum(Transaction.amount), 0.0
                ).label("total"),
            )
            .join(Account, Transaction.account_id == Account.id)
            .outerjoin(Category, Transaction.category_id == Category.id)
            .filter(
                Account.user_id == user_id,
                Transaction.transaction_type == TransactionType.EXPENSE,
            )
            .group_by(name_expr)
        )
        for flt in self._range_filters(start_date, end_date):
            query = query.filter(flt)
        return [
            (row.category_name, float(row.total or 0)) for row in query.all()
        ]

    def summary_daily_totals(
        self,
        user_id: UUID,
        start_date: date | None,
        end_date: date | None,
    ) -> list[tuple[date, float]]:
        net_expr = case(
            (
                Transaction.transaction_type == TransactionType.INCOME,
                Transaction.amount,
            ),
            else_=-Transaction.amount,
        )
        day_expr = func.date_trunc("day", Transaction.transaction_date)
        query = (
            self._db.query(
                day_expr.label("day"),
                functions.coalesce(functions.sum(net_expr), 0.0).label("net"),
            )
            .join(Account, Transaction.account_id == Account.id)
            .filter(Account.user_id == user_id)
            .group_by(day_expr)
            .order_by(day_expr)
        )
        for flt in self._range_filters(start_date, end_date):
            query = query.filter(flt)
        result = []
        for row in query.all():
            day_value = (
                row.day.date() if isinstance(row.day, datetime) else row.day
            )
            result.append((day_value, float(row.net or 0)))
        return result

    def spending_by_category(
        self,
        user_id: UUID,
        start_date: date | None,
        end_date: date | None,
        transaction_type: TransactionType,
    ) -> list[tuple[str, float]]:
        name_expr = functions.coalesce(Category.name, "Інше")
        query = (
            self._db.query(
                name_expr.label("category_name"),
                functions.coalesce(
                    functions.sum(Transaction.amount), 0.0
                ).label("total"),
            )
            .join(Account, Transaction.account_id == Account.id)
            .outerjoin(Category, Transaction.category_id == Category.id)
            .filter(
                Account.user_id == user_id,
                Transaction.transaction_type == transaction_type,
            )
            .group_by(name_expr)
        )
        for flt in self._range_filters(start_date, end_date):
            query = query.filter(flt)
        return [
            (row.category_name, float(row.total or 0)) for row in query.all()
        ]

    def cashflow(
        self,
        user_id: UUID,
        start_date: date | None,
        end_date: date | None,
        interval: Literal["daily", "weekly", "monthly"],
    ) -> list[tuple[datetime, float, float]]:
        if interval == "weekly":
            period_expr = func.date_trunc("week", Transaction.transaction_date)
        elif interval == "monthly":
            period_expr = func.date_trunc("month", Transaction.transaction_date)
        else:
            period_expr = func.date_trunc("day", Transaction.transaction_date)

        income_expr = case(
            (
                Transaction.transaction_type == TransactionType.INCOME,
                Transaction.amount,
            ),
            else_=0.0,
        )
        expense_expr = case(
            (
                Transaction.transaction_type == TransactionType.EXPENSE,
                Transaction.amount,
            ),
            else_=0.0,
        )
        query = (
            self._db.query(
                period_expr.label("period"),
                functions.coalesce(functions.sum(income_expr), 0.0).label(
                    "income"
                ),
                functions.coalesce(functions.sum(expense_expr), 0.0).label(
                    "expense"
                ),
            )
            .join(Account, Transaction.account_id == Account.id)
            .filter(Account.user_id == user_id)
            .group_by(period_expr)
            .order_by(period_expr)
        )
        for flt in self._range_filters(start_date, end_date):
            query = query.filter(flt)
        return [
            (
                row.period,
                float(row.income or 0),
                float(row.expense or 0),
            )
            for row in query.all()
        ]

    def budget_utilization_rows(
        self,
        user_id: UUID,
    ) -> list[tuple[Budget, float]]:
        spent_subquery = (
            self._db.query(
                functions.coalesce(functions.sum(Transaction.amount), 0.0)
            )
            .join(Account, Transaction.account_id == Account.id)
            .filter(
                Account.user_id == user_id,
                Transaction.category_id == Budget.category_id,
                Transaction.transaction_type == TransactionType.EXPENSE,
                Transaction.transaction_date >= Budget.start_date,
                Transaction.transaction_date <= Budget.end_date,
            )
            .correlate(Budget)
            .scalar_subquery()
        )

        rows = (
            self._db.query(Budget, spent_subquery.label("spent_amount"))
            .filter(Budget.user_id == user_id)
            .all()
        )
        return [(row[0], float(row[1] or 0)) for row in rows]

    def anomaly_stats(
        self,
        user_id: UUID,
        start_date: date,
    ) -> tuple[int, float, float | None]:
        query = (
            self._db.query(
                functions.count(Transaction.id),
                func.avg(Transaction.amount),
                func.stddev_pop(Transaction.amount),
            )
            .join(Account, Transaction.account_id == Account.id)
            .filter(
                Account.user_id == user_id,
                Transaction.transaction_type == TransactionType.EXPENSE,
                Transaction.transaction_date
                >= datetime.combine(start_date, time.min, tzinfo=timezone.utc),
            )
        )
        count, mean, stddev = query.one()
        return int(count or 0), float(mean or 0), stddev

    def anomaly_transactions(
        self,
        user_id: UUID,
        start_date: date,
        threshold: float,
    ) -> list[Transaction]:
        return (
            self._db.query(Transaction)
            .join(Account, Transaction.account_id == Account.id)
            .filter(
                Account.user_id == user_id,
                Transaction.transaction_type == TransactionType.EXPENSE,
                Transaction.transaction_date
                >= datetime.combine(start_date, time.min, tzinfo=timezone.utc),
                Transaction.amount > threshold,
            )
            .order_by(Transaction.amount.desc())
            .all()
        )

    def recommendation_income(
        self,
        user_id: UUID,
        start_date: date,
    ) -> float:
        income_sum = (
            self._db.query(
                functions.coalesce(functions.sum(Transaction.amount), 0.0)
            )
            .join(Account, Transaction.account_id == Account.id)
            .filter(
                Account.user_id == user_id,
                Transaction.transaction_type == TransactionType.INCOME,
                Transaction.transaction_date
                >= datetime.combine(start_date, time.min, tzinfo=timezone.utc),
            )
            .scalar()
        )
        return float(income_sum or 0)

    def recommendation_expense_by_category(
        self,
        user_id: UUID,
        start_date: date,
    ) -> list[tuple[str, float]]:
        name_expr = functions.coalesce(Category.name, "Інше")
        query = (
            self._db.query(
                name_expr.label("category_name"),
                functions.coalesce(
                    functions.sum(Transaction.amount), 0.0
                ).label("total"),
            )
            .join(Account, Transaction.account_id == Account.id)
            .outerjoin(Category, Transaction.category_id == Category.id)
            .filter(
                Account.user_id == user_id,
                Transaction.transaction_type == TransactionType.EXPENSE,
                Transaction.transaction_date
                >= datetime.combine(start_date, time.min, tzinfo=timezone.utc),
            )
            .group_by(name_expr)
        )
        return [
            (row.category_name, float(row.total or 0)) for row in query.all()
        ]
