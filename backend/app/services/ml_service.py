import logging
from sqlalchemy.orm import Session
from app.db.models import Category, TransactionType
from ml.models.categorizer import TransactionCategorizer
from shared.config import ml_settings
from uuid import UUID

logger = logging.getLogger(__name__)


class MLService:
    def __init__(self):
        self.categorizer = TransactionCategorizer(ml_settings)
        self._is_loaded = False

    def load_model(self):
        try:
            self.categorizer.load_model()
            self._is_loaded = True
            logger.info("ML model successfully loaded into memory.")
        except FileNotFoundError as e:
            self._is_loaded = False
            logger.warning(
                "Failed to load ML model (File not found). Fallback to manual categorization. Details: %s",
                e,
            )
        except OSError as e:
            self._is_loaded = False
            logger.error("OS Error while loading ML model. Details: %s", e)

    def predict_with_confidence(self, description: str) -> tuple[str, float]:
        if not self._is_loaded:
            return "Uncategorized", 0.0
        return self.categorizer.predict_with_confidence(description)

    def categorize_transaction_description(
        self, db: Session, user_id: UUID, description: str
    ) -> tuple[UUID | None, str, float]:

        label, confidence = self.predict_with_confidence(description)

        if label == "Uncategorized":
            return None, label, 0.0

        category = (
            db.query(Category)
            .filter(
                Category.transaction_type == TransactionType.EXPENSE,
                Category.name.ilike(label),
                (Category.user_id == user_id) | (Category.user_id.is_(None)),
            )
            .first()
        )

        if category:
            logger.info(
                "Model predicted '%s' (%.0f%%). Matched DB category ID: %s",
                label,
                confidence * 100,
                category.id,
            )
            return category.id, label, confidence

        logger.info(
            "Model predicted '%s' (%.0f%%). No match in DB, returning None.",
            label,
            confidence * 100,
        )
        return None, label, confidence


ml_service = MLService()
