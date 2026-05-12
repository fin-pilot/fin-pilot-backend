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

    def predict(self, description: str) -> str:
        if not self._is_loaded:
            return "Uncategorized"

        return self.categorizer.predict([description])[0]

    def categorize_transaction_description(
        self,
        db: Session,
        user_id: UUID,
        description: str,
    ) -> tuple[UUID | None, str]:

        label = self.predict(description)

        if label == "Uncategorized":
            return None, label

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
                "Model predicted '%s'. Matched DB category ID: %s",
                label,
                category.id,
            )

            return category.id, label

        logger.info(
            "Model predicted '%s'. No DB category match found.",
            label,
        )

        return None, label


ml_service = MLService()
