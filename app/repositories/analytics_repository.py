from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Literal
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Account,
    Budget,
    Category,
    Transaction,
    TransactionType,
)


class AnalyticsRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    @staticmethod
    def _range_filters(start: date | None, end: date | None) -> list:
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

        stmt = (
            select(
                func.coalesce(func.sum(income_expr), 0.0),
                func.coalesce(func.sum(expense_expr), 0.0),
            )
            .join(Account, Transaction.account_id == Account.id)
            .where(Account.user_id == user_id)
        )

        for flt in self._range_filters(start_date, end_date):
            stmt = stmt.where(flt)

        income, expense = self._db.execute(stmt).one()

        return float(income or 0), float(expense or 0)

    def summary_by_category(
        self,
        user_id: UUID,
        start_date: date | None,
        end_date: date | None,
    ) -> list[tuple[str, float]]:
        name_expr = func.coalesce(Category.name, "Інше")

        stmt = (
            select(
                name_expr.label("category_name"),
                func.coalesce(func.sum(Transaction.amount), 0.0).label("total"),
            )
            .join(Account, Transaction.account_id == Account.id)
            .outerjoin(Category, Transaction.category_id == Category.id)
            .where(
                Account.user_id == user_id,
                Transaction.transaction_type == TransactionType.EXPENSE,
            )
            .group_by(name_expr)
        )

        for flt in self._range_filters(start_date, end_date):
            stmt = stmt.where(flt)

        rows = self._db.execute(stmt).all()

        return [(row.category_name, float(row.total or 0)) for row in rows]

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

        day_expr = func.date_trunc(
            "day",
            Transaction.transaction_date,
        )

        stmt = (
            select(
                day_expr.label("day"),
                func.coalesce(func.sum(net_expr), 0.0).label("net"),
            )
            .join(Account, Transaction.account_id == Account.id)
            .where(Account.user_id == user_id)
            .group_by(day_expr)
            .order_by(day_expr)
        )

        for flt in self._range_filters(start_date, end_date):
            stmt = stmt.where(flt)

        rows = self._db.execute(stmt).all()

        result: list[tuple[date, float]] = []

        for row in rows:
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
        name_expr = func.coalesce(Category.name, "Інше")

        stmt = (
            select(
                name_expr.label("category_name"),
                func.coalesce(func.sum(Transaction.amount), 0.0).label("total"),
            )
            .join(Account, Transaction.account_id == Account.id)
            .outerjoin(Category, Transaction.category_id == Category.id)
            .where(
                Account.user_id == user_id,
                Transaction.transaction_type == transaction_type,
            )
            .group_by(name_expr)
        )

        for flt in self._range_filters(start_date, end_date):
            stmt = stmt.where(flt)

        rows = self._db.execute(stmt).all()

        return [(row.category_name, float(row.total or 0)) for row in rows]

    def cashflow(
        self,
        user_id: UUID,
        start_date: date | None,
        end_date: date | None,
        interval: Literal["daily", "weekly", "monthly"],
    ) -> list[tuple[datetime, float, float]]:
        if interval == "weekly":
            period_expr = func.date_trunc(
                "week",
                Transaction.transaction_date,
            )
        elif interval == "monthly":
            period_expr = func.date_trunc(
                "month",
                Transaction.transaction_date,
            )
        else:
            period_expr = func.date_trunc(
                "day",
                Transaction.transaction_date,
            )

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

        stmt = (
            select(
                period_expr.label("period"),
                func.coalesce(func.sum(income_expr), 0.0).label("income"),
                func.coalesce(func.sum(expense_expr), 0.0).label("expense"),
            )
            .join(Account, Transaction.account_id == Account.id)
            .where(Account.user_id == user_id)
            .group_by(period_expr)
            .order_by(period_expr)
        )

        for flt in self._range_filters(start_date, end_date):
            stmt = stmt.where(flt)

        rows = self._db.execute(stmt).all()

        return [
            (
                row.period,
                float(row.income or 0),
                float(row.expense or 0),
            )
            for row in rows
        ]

    def budget_utilization_rows(
        self,
        user_id: UUID,
    ) -> list[tuple[Budget, float]]:
        spent_subquery = (
            select(func.coalesce(func.sum(Transaction.amount), 0.0))
            .join(Account, Transaction.account_id == Account.id)
            .where(
                Account.user_id == user_id,
                Transaction.category_id == Budget.category_id,
                Transaction.transaction_type == TransactionType.EXPENSE,
                Transaction.transaction_date >= Budget.start_date,
                Transaction.transaction_date <= Budget.end_date,
            )
            .correlate(Budget)
            .scalar_subquery()
        )

        stmt = select(
            Budget,
            spent_subquery.label("spent_amount"),
        ).where(Budget.user_id == user_id)

        rows = self._db.execute(stmt).all()

        return [(row[0], float(row[1] or 0)) for row in rows]

    def anomaly_stats(
        self,
        user_id: UUID,
        start_date: date,
    ) -> tuple[int, float, float | None]:
        stmt = (
            select(
                func.count(Transaction.id),
                func.avg(Transaction.amount),
                func.stddev_pop(Transaction.amount),
            )
            .join(Account, Transaction.account_id == Account.id)
            .where(
                Account.user_id == user_id,
                Transaction.transaction_type == TransactionType.EXPENSE,
                Transaction.transaction_date
                >= datetime.combine(
                    start_date,
                    time.min,
                    tzinfo=timezone.utc,
                ),
            )
        )

        count, mean, stddev = self._db.execute(stmt).one()

        return (
            int(count or 0),
            float(mean or 0),
            float(stddev) if stddev is not None else None,
        )

    def anomaly_transactions(
        self,
        user_id: UUID,
        start_date: date,
        threshold: float,
    ) -> list[Transaction]:
        stmt = (
            select(Transaction)
            .join(Account, Transaction.account_id == Account.id)
            .where(
                Account.user_id == user_id,
                Transaction.transaction_type == TransactionType.EXPENSE,
                Transaction.transaction_date
                >= datetime.combine(
                    start_date,
                    time.min,
                    tzinfo=timezone.utc,
                ),
                Transaction.amount > threshold,
            )
            .order_by(Transaction.amount.desc())
        )

        return list(self._db.scalars(stmt).all())

    def recommendation_income(
        self,
        user_id: UUID,
        start_date: date,
    ) -> float:
        stmt = (
            select(func.coalesce(func.sum(Transaction.amount), 0.0))
            .join(Account, Transaction.account_id == Account.id)
            .where(
                Account.user_id == user_id,
                Transaction.transaction_type == TransactionType.INCOME,
                Transaction.transaction_date
                >= datetime.combine(
                    start_date,
                    time.min,
                    tzinfo=timezone.utc,
                ),
            )
        )

        income_sum = self._db.scalar(stmt)

        return float(income_sum or 0)

    def recommendation_expense_by_category(
        self,
        user_id: UUID,
        start_date: date,
    ) -> list[tuple[str, float]]:
        name_expr = func.coalesce(Category.name, "Інше")

        stmt = (
            select(
                name_expr.label("category_name"),
                func.coalesce(func.sum(Transaction.amount), 0.0).label("total"),
            )
            .join(Account, Transaction.account_id == Account.id)
            .outerjoin(Category, Transaction.category_id == Category.id)
            .where(
                Account.user_id == user_id,
                Transaction.transaction_type == TransactionType.EXPENSE,
                Transaction.transaction_date
                >= datetime.combine(
                    start_date,
                    time.min,
                    tzinfo=timezone.utc,
                ),
            )
            .group_by(name_expr)
        )

        rows = self._db.execute(stmt).all()

        return [(row.category_name, float(row.total or 0)) for row in rows]
