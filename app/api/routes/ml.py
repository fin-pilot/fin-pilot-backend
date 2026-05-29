from datetime import datetime, timedelta, UTC
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.exceptions import ValidationError
from app.db.database import get_db
from app.db.models import Category, TransactionType, User
from app.schemas.ml import (
    ForecastPoint,
    PredictCategoryRequest,
    PredictCategoryResponse,
    PredictForecastResponse,
    SeasonalityResponse,
)
from app.services.ml_service import ml_service

router = APIRouter(prefix="/api/ml", tags=["machine-learning"])


@router.post("/categorize", response_model=PredictCategoryResponse)
async def categorize_description(
    request: PredictCategoryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    category_id: UUID | None
    label: str

    category_id, label = ml_service.categorize_transaction_description(
        db,
        current_user.id,
        request.description,
    )

    is_fallback = False

    if category_id is None:
        is_fallback = True

        stmt = select(Category).where(
            Category.name == "Other",
            Category.transaction_type == TransactionType.EXPENSE,
            Category.user_id.is_(None),
        )

        fallback_cat = db.execute(stmt).scalars().first()

        if fallback_cat is not None:
            category_id = fallback_cat.id

        message = (
            f"Model predicted '{label}', "
            "but it's not in your DB. Using 'Other'."
        )
    else:
        message = "Success! Predicted category matches your Database."

    return PredictCategoryResponse(
        predicted_category_id=category_id,
        predicted_label=label,
        message=message,
        is_fallback=is_fallback,
    )


@router.post("/forecast/train", status_code=202)
async def train_forecaster(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        success = await ml_service.train_user_forecaster(db, current_user.id)
        if not success:
            raise ValidationError("Недостатньо даних для навчання моделі")
        return {
            "message": "Процес навчання моделі успішно запущено або оновлено"
        }
    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError(f"Помилка при навчанні: {str(e)}") from e


@router.get(
    "/forecast/predict",
    response_model=PredictForecastResponse,
)
async def predict_expenses(
    horizon: int = Query(
        30,
        ge=1,
        le=90,
        description="Кількість днів для прогнозу",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    raw_predictions = ml_service.get_forecast_predictions(
        db,
        current_user.id,
        horizon,
    )

    if not raw_predictions:
        return PredictForecastResponse(
            predictions=[],
            message="Модель ще не навчена або недостатньо даних для прогнозу",
        )

    today = datetime.now(UTC).date()

    predictions = [
        ForecastPoint(
            date=today + timedelta(days=index + 1),
            predicted_amount=amount,
        )
        for index, amount in enumerate(raw_predictions)
    ]

    return PredictForecastResponse(
        predictions=predictions,
        message=f"Прогноз на {horizon} днів сформовано успішно",
    )


@router.get("/forecast/seasonality", response_model=SeasonalityResponse)
async def get_seasonality_patterns(
    current_user: User = Depends(get_current_user),
):
    patterns = ml_service.get_user_seasonality(current_user.id)

    if not patterns:
        raise ValidationError("Сезонні патерни ще не визначені")

    return SeasonalityResponse(
        user_id=current_user.id,
        seasonal_patterns=patterns,
        message="Сезонні патерни успішно вилучено з моделі",
    )
