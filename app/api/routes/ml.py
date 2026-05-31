"""ML API routes.

/api/ml/categorize         POST  — classify a transaction description
/api/ml/forecast/train     POST  — trigger per-user SARIMA training (async, 202)
/api/ml/forecast/predict   GET   — weekly expense forecast from per-user model
/api/ml/status             GET   — model load state + training progress
/api/ml/metrics            GET   — evaluation metrics (F1, MAE, RMSE …) from artifacts
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.exceptions import ValidationError
from app.db.database import get_db
from app.db.models import Category, TransactionType, User
from app.schemas.ml import (
    ForecastStatusResponse,
    MLStatusResponse,
    ModelMetricsResponse,
    PredictCategoryRequest,
    PredictCategoryResponse,
    WeeklyForecastPoint,
)
from app.services.ml_service import backend_ml_service
from sqlalchemy import select

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ml", tags=["machine-learning"])


# ── Categorisation ─────────────────────────────────────────────────────────

@router.post("/categorize", response_model=PredictCategoryResponse)
async def categorize_description(
    request: PredictCategoryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Classify *description* using rule-based lookup then ML model."""
    category_id, label, confidence = backend_ml_service.categorise_description(
        db, current_user.id, request.description
    )

    is_fallback = category_id is None

    if is_fallback:
        # Try to resolve the "Other" fallback category
        fallback = db.execute(
            select(Category).where(
                Category.name == "Other",
                Category.transaction_type == TransactionType.EXPENSE,
                Category.user_id.is_(None),
            )
        ).scalars().first()
        if fallback is not None:
            category_id = fallback.id
        message = (
            f"Model predicted '{label}', "
            "but no matching category found in DB. Using 'Other'."
        )
    else:
        message = "Success — predicted category matched the database."

    return PredictCategoryResponse(
        predicted_category_id=category_id,
        predicted_label=label,
        confidence=confidence,
        message=message,
        is_fallback=is_fallback,
    )


# ── Forecasting ────────────────────────────────────────────────────────────

@router.post("/forecast/train", status_code=202)
async def train_forecaster(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger per-user SARIMA training.

    Returns ``202 Accepted`` immediately.  Training runs in the background.
    Poll ``GET /api/ml/status`` to check progress.
    """
    started = await backend_ml_service.train_forecaster(db, current_user.id)
    if not started:
        raise ValidationError(
            "Недостатньо даних для навчання моделі. "
            "Додайте більше транзакцій витрат і спробуйте знову."
        )
    return {
        "message": "Навчання моделі розпочато. "
                   "Перевіряйте статус через GET /api/ml/status."
    }


@router.get("/forecast/predict", response_model=ForecastStatusResponse)
async def predict_expenses(
    horizon: int = Query(
        4,
        ge=1,
        le=52,
        description="Кількість тижнів для прогнозу (1–52)",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a weekly expense forecast using the per-user SARIMA model."""
    import asyncio

    ml_resp = await asyncio.to_thread(
        backend_ml_service.predict_weekly_expenses,
        current_user.id,
        horizon,
        db,
    )

    return ForecastStatusResponse(
        is_cold_start=ml_resp.is_cold_start,
        model_used=ml_resp.model_used,
        weeks=[
            WeeklyForecastPoint(
                week_start=pt.week_start,
                predicted_expense=pt.predicted_expense,
            )
            for pt in ml_resp.weeks
        ],
        generated_at=ml_resp.generated_at,
        base_currency=current_user.base_currency,
    )


# ── Status ─────────────────────────────────────────────────────────────────

@router.get("/status", response_model=MLStatusResponse)
async def ml_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return model load state and training progress for the current user."""
    state = backend_ml_service.get_training_status(db, current_user.id)

    sarima_loaded = False
    if state and state.sarima_model_path:
        sarima_loaded = Path(state.sarima_model_path).exists()

    return MLStatusResponse(
        categoriser_loaded=backend_ml_service.categoriser_loaded,
        sarima_loaded=sarima_loaded,
        training_status=state.training_status.value if state else None,
        last_trained_at=(
            state.last_trained_at.isoformat() if state and state.last_trained_at else None
        ),
        n_training_samples=state.n_training_samples if state else None,
        error_message=state.error_message if state else None,
        base_currency=current_user.base_currency,
    )


# ── Academic evaluation metrics ─────────────────────────────────────────────

@router.get("/metrics", response_model=ModelMetricsResponse)
async def get_model_metrics(
    current_user: User = Depends(get_current_user),
):
    """Return evaluation metrics produced during model training.

    Reads JSON artefacts written by the ML training pipelines:
    - ``artifacts/categorizing/evaluation/metrics.json``  (F1, Precision, Recall, MCC)
    - ``artifacts/evaluation/sarima_metrics.json``         (MAE, RMSE, WAPE, SMAPE)
    """
    categoriser_metrics: dict | None = _load_json(
        Path("artifacts/categorizing/evaluation/metrics.json")
    )
    forecasting_metrics: dict | None = _load_json(
        Path("artifacts/evaluation/sarima_metrics.json")
    )

    return ModelMetricsResponse(
        categoriser=categoriser_metrics,
        forecasting=forecasting_metrics,
    )


# ── Helpers ────────────────────────────────────────────────────────────────

def _load_json(path: Path) -> dict | None:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        logger.debug("Metrics file not found: %s", path)
        return None
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read metrics from %s: %s", path, exc)
        return None
