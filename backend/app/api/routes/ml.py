from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.api.dependencies import get_current_user
from app.db.models import User, Category, TransactionType
from app.services.ml_service import ml_service
from app.schemas.transaction import (
    PredictCategoryRequest,
    PredictCategoryResponse,
)

router = APIRouter(prefix="/api/ml", tags=["Machine Learning"])


@router.post("/categorize", response_model=PredictCategoryResponse)
async def categorize_description(
    request: PredictCategoryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    category_id, label, confidence = (
        ml_service.categorize_transaction_description(
            db, current_user.id, request.description
        )
    )

    is_fallback = False

    if not category_id:
        is_fallback = True
        fallback_cat = (
            db.query(Category)
            .filter(
                Category.name == "Other",
                Category.transaction_type == TransactionType.EXPENSE,
                Category.user_id.is_(None),
            )
            .first()
        )

        if fallback_cat:
            category_id = fallback_cat.id

        message = f"Model predicted '{label}', but it's not in your DB. Using 'Other'."
    else:
        message = "Success! Predicted category matches your Database."

    return PredictCategoryResponse(
        predicted_category_id=category_id,
        predicted_label=label,
        confidence_score=confidence,
        message=message,
        is_fallback=is_fallback,
    )
