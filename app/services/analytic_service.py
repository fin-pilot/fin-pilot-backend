from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import TransactionType
from app.i18n.translator import t, translate_category
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.forecast_repository import ForecastRepository
from app.schemas.analytics import (
    AnomalyItem,
    BudgetUtilization,
    CashflowData,
    CategorySpending,
    DailyTotal,
    ForecastResponse,
    RecommendationItem,
    RecommendationsResponse,
    SummaryResponse,
)
from app.services.ml_service import backend_ml_service


class AnalyticsService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = AnalyticsRepository(db)
        self._forecast_repo = ForecastRepository(db)

    def summary(
        self,
        user_id: UUID,
        start_date: date | None,
        end_date: date | None,
    ) -> SummaryResponse:
        income, expense = self._repo.summary_totals(
            user_id, start_date, end_date
        )
        by_category_rows = self._repo.summary_by_category(
            user_id, start_date, end_date
        )
        daily_totals_rows = self._repo.summary_daily_totals(
            user_id, start_date, end_date
        )

        by_category = {name: amount for name, amount in by_category_rows}
        daily_totals = [
            DailyTotal(
                date=day.isoformat(),
                amount=amount,
            )
            for day, amount in daily_totals_rows
        ]

        return SummaryResponse(
            total_income=income,
            total_expenses=expense,
            net_balance=income - expense,
            by_category=by_category,
            daily_totals=daily_totals,
        )

    def spending_by_category(
        self,
        user_id: UUID,
        start_date: date | None,
        end_date: date | None,
        transaction_type: str,
    ) -> list[CategorySpending]:
        tx_type = self._parse_transaction_type(transaction_type)
        rows = self._repo.spending_by_category(
            user_id, start_date, end_date, tx_type
        )

        total = sum(amount for _, amount in rows)
        result = [
            CategorySpending(
                category_name=name,
                amount=round(amount, 2),
                percentage=(
                    round((amount / total * 100), 2) if total > 0 else 0.0
                ),
            )
            for name, amount in rows
        ]
        result.sort(key=lambda x: x.amount, reverse=True)
        return result

    def cashflow(
        self,
        user_id: UUID,
        start_date: date | None,
        end_date: date | None,
        interval: Literal["daily", "weekly", "monthly"],
    ) -> list[CashflowData]:
        rows = self._repo.cashflow(user_id, start_date, end_date, interval)
        if not rows:
            return []

        results: list[CashflowData] = []
        for period, income, expense in rows:
            label_date = self._format_period_label(period, interval)
            results.append(
                CashflowData(
                    date=label_date,
                    income=round(income, 2),
                    expense=round(expense, 2),
                )
            )
        return results

    def budget_utilization(self, user_id: UUID) -> list[BudgetUtilization]:
        rows = self._repo.budget_utilization_rows(user_id)
        result: list[BudgetUtilization] = []
        for budget, spent in rows:
            pct = (
                (spent / budget.limit_amount * 100)
                if budget.limit_amount
                else 0.0
            )
            status = (
                "green" if pct < 75.0 else ("yellow" if pct <= 100.0 else "red")
            )
            result.append(
                BudgetUtilization(
                    budget_id=budget.id,
                    budget_name=budget.name,
                    amount_limit=budget.limit_amount,
                    spent_amount=spent,
                    percentage=round(pct, 2),
                    status=status,
                )
            )
        return result

    def list_forecast(self, user_id: UUID) -> list[ForecastResponse]:
        """Return stored forecast rows (written after each training run)."""
        rows = self._forecast_repo.list_by_user(user_id)
        return [ForecastResponse.from_forecast_row(row) for row in rows]

    def anomalies(self, user_id: UUID, window_days: int) -> list[AnomalyItem]:
        start_date = date.today() - timedelta(days=window_days)
        count, mean_amt, std_dev = self._repo.anomaly_stats(user_id, start_date)
        if count < 5 or std_dev is None or std_dev < 1:
            return []

        high_threshold = mean_amt + (3 * std_dev)
        medium_threshold = mean_amt + (2 * std_dev)

        rows = self._repo.anomaly_transactions(
            user_id, start_date, medium_threshold
        )
        anomalies: list[AnomalyItem] = []
        for tx in rows:
            level = "high" if tx.amount > high_threshold else "medium"
            anomalies.append(
                AnomalyItem(
                    transaction_id=tx.id,
                    date=tx.transaction_date.date().isoformat(),
                    description=tx.description or "Невідома",
                    amount=round(tx.amount, 2),
                    anomaly_level=level,
                )
            )
        return anomalies

    def recommendations(self, user_id: UUID, locale: str = "uk") -> RecommendationsResponse:
        """Generate three-tier financial recommendations via the ML engine."""
        ml_response = backend_ml_service.get_ml_recommendations(
            self._db, user_id
        )

        items = [
            RecommendationItem(
                tier=rec.tier,
                category=_localize_category_name(rec.category, locale, self._db),
                diagnosis=_translate_rec_field(rec, "diagnosis", locale, self._db),
                action=_translate_rec_field(rec, "action", locale, self._db),
                projected_effect=_translate_rec_field(rec, "projected_effect", locale, self._db),
                confidence=rec.confidence,
            )
            for rec in ml_response.recommendations
        ]

        return RecommendationsResponse(
            recommendations=items,
            generated_at=ml_response.generated_at,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _parse_transaction_type(raw: str) -> TransactionType:
        key = raw.strip().lower()
        mapping = {
            "income": TransactionType.INCOME,
            "expense": TransactionType.EXPENSE,
            "transfer": TransactionType.TRANSFER,
        }
        return mapping.get(key, TransactionType.EXPENSE)

    @staticmethod
    def _format_period_label(
        period_value, interval: Literal["daily", "weekly", "monthly"]
    ) -> str:
        if hasattr(period_value, "date"):
            period_date = period_value.date()
        else:
            period_date = period_value

        if interval == "weekly":
            label_date = period_date + timedelta(days=6)
            return label_date.isoformat()

        if interval == "monthly":
            last_day = calendar.monthrange(period_date.year, period_date.month)[1]
            return period_date.replace(day=last_day).isoformat()

        return period_date.isoformat()


# ── Module-level i18n helpers ─────────────────────────────────────────────────

# Maps the English ML-internal category names to their i18n slugs.
# Keeps ML logic fully locale-agnostic while allowing the API layer to localize.
_ML_NAME_TO_SLUG: dict[str, str] = {
    "Food & Dining":              "food_dining",
    "Transportation":             "transportation",
    "Shopping & Retail":          "shopping_retail",
    "Entertainment & Recreation": "entertainment",
    "Healthcare & Medical":       "healthcare",
    "Utilities & Services":       "utilities",
    "Financial Services":         "financial_services",
    "Government & Legal":         "government_legal",
    "Charity & Donations":        "charity",
    "Income":                     "income_general",
    "Investments":                "investments",
    "Salary":                     "salary",
    "general":                    "general",
}


def _fmt(value: float) -> str:
    """Format a float amount as a compact decimal string (no currency symbol)."""
    return f"{value:,.2f}"


def _localize_category_name(
    english_name: str,
    locale: str,
    db: Session | None = None,
) -> str:
    """Return the localized display name for an ML-internal English category name.

    Resolution order:
    1. Static slug map (covers all 14 default categories, zero DB calls).
    2. DB lookup via ``Category.slug`` (covers user-created categories).
    3. Original English name (safe fallback, never raises).
    """
    slug = _ML_NAME_TO_SLUG.get(english_name)
    if slug:
        localized = translate_category(slug, locale)
        if localized and localized != f"categories.{slug}":
            return localized

    if db is not None:
        from app.db.models import Category as _Category
        from sqlalchemy import select as _select
        row = db.execute(
            _select(_Category.slug).where(_Category.name == english_name)
        ).scalar_one_or_none()
        if row:
            localized = translate_category(row, locale)
            if localized and localized != f"categories.{row}":
                return localized

    return english_name


def _translate_rec_field(
    rec: object,
    field: str,
    locale: str,
    db: Session | None = None,
) -> str:
    """Return a locale-rendered string for diagnosis/action/projected_effect.

    Translates the ``{category}`` template variable so Ukrainian users see
    «Їжа та харчування» instead of «Food & Dining».
    """
    if not getattr(rec, "rule_key", None):
        return getattr(rec, field)

    template_vars: dict = getattr(rec, "template_vars", {})

    formatted_vars: dict = {}
    for k, v in template_vars.items():
        if k == "category" and isinstance(v, str):
            formatted_vars[k] = _localize_category_name(v, locale, db)
        elif isinstance(v, float):
            formatted_vars[k] = _fmt(v)
        else:
            formatted_vars[k] = v

    key = f"recommendations.{rec.rule_key}.{field}"
    translated = t(key, locale=locale, **formatted_vars)
    if translated == key:
        return getattr(rec, field)
    return translated
