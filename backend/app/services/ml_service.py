import logging
import re
from uuid import UUID

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import (
    Category,
    Transaction,
    TransactionType,
    UserTransactionRule,
)
from ml.models.categorizer import TransactionCategorizer
from ml.models.forecaster import ExpenseForecaster
from shared.config import ml_settings

logger = logging.getLogger(__name__)


class MLService:
    def __init__(self):
        self.categorizer = TransactionCategorizer(ml_settings)

        self.forecaster = ExpenseForecaster(ml_settings)

        self._is_categorizer_loaded = False
        self._is_forecaster_loaded = False

    def load_model(self):
        self.load_categorizer_model()
        self.load_forecaster_model()

    def load_categorizer_model(self):
        try:
            self.categorizer.load_model()

            self._is_categorizer_loaded = True

            logger.info("Categorizer model successfully loaded into memory.")

        except FileNotFoundError as error:
            self._is_categorizer_loaded = False

            logger.warning(
                "Failed to load categorizer model "
                "(File not found). "
                "Fallback to manual categorization. "
                "Details: %s",
                error,
            )

        except OSError as error:
            self._is_categorizer_loaded = False

            logger.error(
                "OS Error while loading categorizer model. " "Details: %s",
                error,
            )

    def load_forecaster_model(self):
        try:
            self.forecaster.load_model()

            self._is_forecaster_loaded = self.forecaster.model is not None

            if self._is_forecaster_loaded:
                logger.info(
                    "Forecasting model successfully loaded into memory."
                )

            else:
                logger.warning("Forecasting model file not found.")

        except FileNotFoundError as error:
            self._is_forecaster_loaded = False

            logger.warning(
                "Failed to load forecasting model "
                "(File not found). "
                "Details: %s",
                error,
            )

        except OSError as error:
            self._is_forecaster_loaded = False

            logger.error(
                "OS Error while loading forecasting model. " "Details: %s",
                error,
            )

    def predict(
        self,
        description: str,
    ) -> str:
        if not self._is_categorizer_loaded:
            return "Uncategorized"

        return self.categorizer.predict([description])[0]

    def _extract_keyword(
        self,
        description: str,
    ) -> str:
        if not description:
            return ""

        text = re.sub(
            r"\d+",
            "",
            description,
        )

        text = re.sub(
            r"[^\w\s]",
            " ",
            text,
        )

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
            return (
                rule.category_id,
                "rule-based",
            )

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
        self,
        db: Session,
        user_id: UUID,
        description: str,
        category_id: UUID,
    ):
        keyword = self._extract_keyword(description)

        if not keyword:
            logger.warning(
                "Could not extract keyword " "from description: %s",
                description,
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
                    "Updating rule: '%s' now maps to %s",
                    keyword,
                    category_id,
                )

                existing_rule.category_id = category_id

                db.add(existing_rule)

        else:
            logger.info(
                "Creating new rule: '%s' -> %s",
                keyword,
                category_id,
            )

            new_rule = UserTransactionRule(
                user_id=user_id,
                keyword=keyword,
                category_id=category_id,
            )

            db.add(new_rule)

        return keyword

    async def train_user_forecaster(
        self,
        db: Session,
        user_id: UUID,
    ) -> bool:
        logger.info(
            "Starting forecasting training for user %s",
            user_id,
        )

        transactions = (
            db.query(
                Transaction.date,
                Transaction.amount,
            )
            .filter(
                Transaction.user_id == user_id,
                Transaction.transaction_type == TransactionType.EXPENSE,
            )
            .order_by(Transaction.date.asc())
            .all()
        )

        if not transactions:
            logger.warning(
                "No expense transactions found " "for user %s",
                user_id,
            )

            return False

        df = pd.DataFrame(
            [
                {
                    "date": transaction.date,
                    "amount": float(transaction.amount),
                }
                for transaction in transactions
            ]
        )

        if self._is_forecaster_loaded and self.forecaster.model is not None:
            logger.info(
                "Updating existing forecasting " "model for user %s",
                user_id,
            )

            success = self.forecaster.update(df)

        else:
            logger.info(
                "Training new forecasting " "model for user %s",
                user_id,
            )

            success = self.forecaster.train(df)

        if not success:
            logger.warning(
                "Forecast training/update failed " "for user %s",
                user_id,
            )

            return False

        self.forecaster.save_model()

        self._is_forecaster_loaded = True

        logger.info(
            "Forecasting model trained/updated "
            "and saved successfully for user %s",
            user_id,
        )

        return True

    def get_forecast_predictions(
        self,
        db: Session,
        user_id: UUID,
        horizon: int,
    ) -> list[float]:
        if not self._is_forecaster_loaded or self.forecaster.model is None:
            logger.warning("Forecast model is not loaded.")

            return []

        logger.info(
            "Generating forecast for user %s " "for %d periods",
            user_id,
            horizon,
        )

        predictions = self.forecaster.predict(horizon)

        return predictions

    def get_user_seasonality(
        self,
        user_id: UUID,
    ) -> dict | None:
        if not self._is_forecaster_loaded or self.forecaster.model is None:
            logger.warning("Seasonality requested but " "model is not loaded.")

            return None

        try:
            model = self.forecaster.model

            return {
                "order": model.order,
                "seasonal_order": (model.seasonal_order),
                "seasonal_period": (model.seasonal_order[-1]),
            }

        except (
            AttributeError,
            ValueError,
            TypeError,
        ) as error:
            logger.error(
                "Failed to extract seasonality: %s",
                error,
            )

            return None


ml_service = MLService()
