"""Academic endpoints for diploma defense support.

These endpoints aggregate system metrics and training logs in a format
that can be directly cited in the diploma report and weekly training diary.

Endpoints
---------
GET /api/academic/metrics   — formatted ML evaluation metrics (Table 2.3 / Table 2.5)
GET /api/academic/diary     — weekly usage & ML retraining log for diary export
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import (
    Account,
    Transaction,
    TransactionType,
    User,
    UserMLState,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/academic", tags=["academic"])


# ── Pydantic response schemas ─────────────────────────────────────────────────

class ClassifierMetrics(BaseModel):
    """Classification quality metrics — Table 2.3 of the diploma report."""

    accuracy: Optional[float] = Field(None, description="Зважена точність (macro avg)")
    precision: Optional[float] = Field(None, description="Зважена Precision")
    recall: Optional[float] = Field(None, description="Зважений Recall")
    f1_score: Optional[float] = Field(None, description="Зважений F1-score")
    mcc: Optional[float] = Field(None, description="Коефіцієнт кореляції Метьюза")
    kappa: Optional[float] = Field(None, description="Статистика Коена Kappa")
    dataset: str = Field("mitulshah/transaction-categorization", description="Навчальний датасет")
    algorithm: str = Field("LinearSVC + TF-IDF (1,2)-gram", description="Алгоритм класифікації")
    train_test_split: str = Field("80/20 зі стратифікацією", description="Розбиття на вибірки")


class ForecastingMetrics(BaseModel):
    """Forecasting quality metrics — Table 2.5 of the diploma report."""

    mae: Optional[float] = Field(None, description="Середня абсолютна похибка (MAE)")
    rmse: Optional[float] = Field(None, description="Середньоквадратична похибка (RMSE)")
    mse: Optional[float] = Field(None, description="Середня квадратична похибка (MSE)")
    wape: Optional[float] = Field(None, description="Зважена абсолютна відсоткова похибка (WAPE), %")
    smape: Optional[float] = Field(None, description="Симетрична MAPE (SMAPE), %")
    n_test_weeks: Optional[int] = Field(None, description="Кількість тестових тижнів")
    n_train_weeks: Optional[int] = Field(None, description="Кількість тренувальних тижнів")
    sarima_order: Optional[list[int]] = Field(None, description="ARIMA-порядок (p,d,q)")
    sarima_seasonal_order: Optional[list[int]] = Field(None, description="Сезонний порядок (P,D,Q,s)")
    algorithm: str = Field("SARIMA", description="Алгоритм прогнозування")
    seasonal_period: int = Field(4, description="Сезонний цикл (тижнів)")


class AcademicMetricsResponse(BaseModel):
    """Combined ML metrics for the diploma experimental section."""

    classifier: ClassifierMetrics
    forecasting: ForecastingMetrics
    report_ready: bool = Field(
        description="True if both metric sets are populated and suitable for the report."
    )
    generated_at: str = Field(description="UTC ISO-8601 timestamp")


class DiaryEntry(BaseModel):
    """One week of recorded system activity for the training diary."""

    week: str = Field(description="ISO week identifier, e.g. '2026-W22'")
    transactions_added: int
    ml_training_triggered: bool
    model_status: Optional[str]
    last_trained_at: Optional[str]
    n_training_samples: Optional[int]
    accounts_active: int
    notes: str


class AcademicDiaryResponse(BaseModel):
    """Weekly training diary export — ready for copy-paste into the diary template."""

    student: str
    group: str = "КА-24"
    topic: str = "Розробка системи управління особистими фінансами з використанням методів прогнозування часових рядів"
    supervisor: str = "доцент, к.т.н. Гуськова В.Г."
    weeks: list[DiaryEntry]
    system_summary: dict[str, Any]
    generated_at: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_json_artifact(path: Path) -> dict | None:
    """Safely load a JSON artifact file."""
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read artifact %s: %s", path, exc)
        return None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/metrics", response_model=AcademicMetricsResponse)
def get_academic_metrics(
    current_user: User = Depends(get_current_user),
) -> AcademicMetricsResponse:
    """Return ML evaluation metrics formatted for the diploma experimental section.

    Reads artifact JSON files produced by training pipelines.  Returns
    ``report_ready=True`` only when both classifier and forecasting metrics
    are fully populated — the diploma committee criterion.
    """
    cat_raw = _load_json_artifact(Path("artifacts/categorizing/evaluation/metrics.json"))
    fc_raw = _load_json_artifact(Path("artifacts/evaluation/sarima_metrics.json"))

    classifier = ClassifierMetrics(
        accuracy=cat_raw.get("accuracy") if cat_raw else None,
        precision=cat_raw.get("precision") if cat_raw else None,
        recall=cat_raw.get("recall") if cat_raw else None,
        f1_score=cat_raw.get("f1_score") if cat_raw else None,
        mcc=cat_raw.get("mcc") if cat_raw else None,
        kappa=cat_raw.get("kappa") if cat_raw else None,
    )

    forecasting = ForecastingMetrics(
        mae=fc_raw.get("mae") if fc_raw else None,
        rmse=fc_raw.get("rmse") if fc_raw else None,
        mse=fc_raw.get("mse") if fc_raw else None,
        wape=fc_raw.get("wape") if fc_raw else None,
        smape=fc_raw.get("smape") if fc_raw else None,
        n_test_weeks=fc_raw.get("n_test_weeks") if fc_raw else None,
        n_train_weeks=fc_raw.get("n_train_weeks") if fc_raw else None,
        sarima_order=fc_raw.get("sarima_order") if fc_raw else None,
        sarima_seasonal_order=fc_raw.get("sarima_seasonal_order") if fc_raw else None,
    )

    report_ready = (
        classifier.f1_score is not None
        and forecasting.mae is not None
        and forecasting.rmse is not None
    )

    return AcademicMetricsResponse(
        classifier=classifier,
        forecasting=forecasting,
        report_ready=report_ready,
        generated_at=datetime.now(tz=timezone.utc).isoformat(),
    )


@router.get("/diary", response_model=AcademicDiaryResponse)
def get_academic_diary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AcademicDiaryResponse:
    """Export a weekly activity log for the pre-diploma training diary.

    Aggregates the last 8 weeks of transaction insertions, model retraining
    events, and account activity into a structured report that can be
    directly pasted into the diary template required by KPI.
    """
    now = datetime.now(tz=timezone.utc)
    ml_state: UserMLState | None = db.execute(
        select(UserMLState).where(UserMLState.user_id == current_user.id)
    ).scalar_one_or_none()

    # ── Per-week transaction counts (last 8 weeks) ─────────────────────────
    weeks: list[DiaryEntry] = []
    for week_offset in range(7, -1, -1):
        week_start = (now - timedelta(weeks=week_offset + 1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        week_end = week_start + timedelta(weeks=1)

        tx_count: int = db.execute(
            select(func.count(Transaction.id))
            .join(Account, Transaction.account_id == Account.id)
            .where(
                Account.user_id == current_user.id,
                Transaction.transaction_date >= week_start,
                Transaction.transaction_date < week_end,
            )
        ).scalar() or 0

        iso_week = week_start.strftime("%G-W%V")

        trained_this_week = (
            ml_state is not None
            and ml_state.last_trained_at is not None
            and week_start <= ml_state.last_trained_at < week_end
        )

        notes_parts = []
        if tx_count > 0:
            notes_parts.append(f"Внесено {tx_count} транзакцій.")
        if trained_this_week:
            notes_parts.append("Виконано навчання моделі SARIMA.")
        if not notes_parts:
            notes_parts.append("Поточний тиждень відсутні нові операції.")

        weeks.append(
            DiaryEntry(
                week=iso_week,
                transactions_added=tx_count,
                ml_training_triggered=trained_this_week,
                model_status=ml_state.training_status.value if ml_state else None,
                last_trained_at=(
                    ml_state.last_trained_at.isoformat()
                    if ml_state and ml_state.last_trained_at
                    else None
                ),
                n_training_samples=ml_state.n_training_samples if ml_state else None,
                accounts_active=db.execute(
                    select(func.count(Account.id)).where(Account.user_id == current_user.id)
                ).scalar() or 0,
                notes=" ".join(notes_parts),
            )
        )

    # ── System-wide summary ────────────────────────────────────────────────
    total_transactions = db.execute(
        select(func.count(Transaction.id))
        .join(Account, Transaction.account_id == Account.id)
        .where(Account.user_id == current_user.id)
    ).scalar() or 0

    income_total = db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .join(Account, Transaction.account_id == Account.id)
        .where(
            Account.user_id == current_user.id,
            Transaction.transaction_type == TransactionType.INCOME,
        )
    ).scalar() or 0

    expense_total = db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .join(Account, Transaction.account_id == Account.id)
        .where(
            Account.user_id == current_user.id,
            Transaction.transaction_type == TransactionType.EXPENSE,
        )
    ).scalar() or 0

    fc_raw = _load_json_artifact(Path("artifacts/evaluation/sarima_metrics.json"))
    cat_raw = _load_json_artifact(Path("artifacts/categorizing/evaluation/metrics.json"))

    system_summary = {
        "total_transactions": total_transactions,
        "income_total_uah": round(float(income_total), 2),
        "expense_total_uah": round(float(expense_total), 2),
        "net_balance_uah": round(float(income_total) - float(expense_total), 2),
        "model_trained": ml_state is not None and ml_state.training_status.value == "ready",
        "sarima_mae": fc_raw.get("mae") if fc_raw else None,
        "sarima_rmse": fc_raw.get("rmse") if fc_raw else None,
        "classifier_f1": cat_raw.get("f1_score") if cat_raw else None,
        "base_currency": current_user.base_currency,
        "locale": current_user.locale,
    }

    return AcademicDiaryResponse(
        student=current_user.full_name or current_user.email,
        weeks=weeks,
        system_summary=system_summary,
        generated_at=now.isoformat(),
    )
