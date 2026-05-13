import logging
import re
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db.models import Category, TransactionType, UserTransactionRule
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

    def _extract_keyword(self, description: str) -> str:
        if not description:
            return ""

        text = re.sub(r"\d+", "", description)
        text = re.sub(r"[^\w\s]", " ", text)
        words = [word.upper() for word in text.split() if len(word) > 1]

        return " ".join(words).strip()

    def categorize_transaction_description(
        self,
        db: Session,
        user_id: UUID,
        description: str,
    ) -> tuple[UUID | None, str]:
        rule = (
            db.query(UserTransactionRule)
            .filter(
                UserTransactionRule.user_id == user_id,
                func.upper(description).contains(
                    func.upper(UserTransactionRule.keyword)
                ),
            )
            .order_by(func.length(UserTransactionRule.keyword).desc())
            .first()
        )

        if rule:
            return rule.category_id, "rule-based"

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
            return category.id, label

        return None, label

    def learn_from_user(
        self, db: Session, user_id: UUID, description: str, category_id: UUID
    ):
        keyword = self._extract_keyword(description)

        if not keyword:
            logger.warning(
                "Could not extract keyword from description: %s", description
            )
            return None

        existing_rule = (
            db.query(UserTransactionRule)
            .filter(
                UserTransactionRule.user_id == user_id,
                UserTransactionRule.keyword == keyword,
            )
            .first()
        )

        if existing_rule:
            if existing_rule.category_id != category_id:
                logger.info(
                    "Updating rule: '%s' now maps to %s", keyword, category_id
                )
                existing_rule.category_id = category_id
                db.add(existing_rule)
        else:
            logger.info("Creating new rule: '%s' -> %s", keyword, category_id)
            new_rule = UserTransactionRule(
                user_id=user_id, keyword=keyword, category_id=category_id
            )
            db.add(new_rule)

        return keyword


ml_service = MLService()
