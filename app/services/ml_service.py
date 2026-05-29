import logging
import re
from uuid import UUID

import joblib
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fin_pilot_ml.categorizing.config import CategorizingConfig
from fin_pilot_ml.categorizing.model import TransactionCategorizer
from fin_pilot_ml.forecasting.models import ForecastModels 

from app.utils.model_loader import CATEGORIZER_MODEL_PATH, FORECASTER_MODEL_PATH

from app.db.models import (
    Category,
    Transaction,
    TransactionType,
    UserTransactionRule,
)

logger = logging.getLogger(__name__)


class MLService:
    def __init__(self) -> None:
        categorizer_config = CategorizingConfig()
        self.categorizer = TransactionCategorizer(categorizer_config)
        self.forecaster_model = None

        self._is_categorizer_loaded = False
        self._is_forecaster_loaded = False

    def load_model(self) -> None:
        self.load_categorizer_model()
        self.load_forecaster_model()

    def load_categorizer_model(self) -> None:
        try:
            self.categorizer.pipeline = joblib.load(CATEGORIZER_MODEL_PATH)
            self._is_categorizer_loaded = True
            logger.info("Categorizer model successfully loaded into memory.")
        except FileNotFoundError as error:
            self._is_categorizer_loaded = False
            logger.warning(
                "Failed to load categorizer model (File not found). "
                "Fallback to manual categorization. Details: %s",
                error,
            )
        except OSError as error:
            self._is_categorizer_loaded = False
            logger.error(
                "OS Error while loading categorizer model. Details: %s",
                error,
            )

    def load_forecaster_model(self) -> None:
        try:
            self.forecaster_model = joblib.load(FORECASTER_MODEL_PATH)
            self._is_forecaster_loaded = True
            logger.info("Forecasting model successfully loaded into memory.")
        except FileNotFoundError as error:
            self._is_forecaster_loaded = False
            logger.warning(
                "Failed to load forecasting model (File not found). Details: %s",
                error,
            )
        except OSError as error:
            self._is_forecaster_loaded = False
            logger.error(
                "OS Error while loading forecasting model. Details: %s",
                error,
            )

    def predict(self, description: str) -> str:
        if not self._is_categorizer_loaded:
            return "Uncategorized"
        
        return self.categorizer.predict([description])[0]

    @staticmethod
    def _extract_keyword(description: str) -> str:
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
        stmt_rule = (
            select(UserTransactionRule)
            .where(
                UserTransactionRule.user_id == user_id,
                func.upper(description).contains(
                    func.upper(UserTransactionRule.keyword)
                ),
            )
            .order_by(func.length(UserTransactionRule.keyword).desc())
        )

        rule: UserTransactionRule | None = db.execute(stmt_rule).scalars().first()

        if rule:
            return rule.category_id, "rule-based"

        label = self.predict(description)

        if label == "Uncategorized":
            return None, label

        stmt_cat = select(Category).where(
            Category.transaction_type == TransactionType.EXPENSE,
            Category.name.ilike(label),
            (Category.user_id == user_id) | (Category.user_id.is_(None)),
        )

        category: Category | None = db.execute(stmt_cat).scalars().first()

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
            logger.warning("Could not extract keyword from description: %s", description)
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
                logger.info("Updating rule: '%s' now maps to %s", keyword, category_id)
                existing_rule.category_id = category_id
                db.add(existing_rule)
        else:
            logger.info("Creating new rule: '%s' -> %s", keyword, category_id)
            new_rule = UserTransactionRule(
                user_id=user_id,
                keyword=keyword,
                category_id=category_id,
            )
            db.add(new_rule)

        return keyword

    async def train_user_forecaster(self, db: Session, user_id: UUID) -> bool:
        logger.info("Starting forecasting training for user %s", user_id)

        transactions = (
            db.query(Transaction.transaction_date, Transaction.amount)
            .filter(
                Transaction.account.user_id == user_id,
                Transaction.transaction_type == TransactionType.EXPENSE,
            )
            .order_by(Transaction.transaction_date.asc())
            .all()
        )

        if not transactions:
            logger.warning("No expense transactions found for user %s", user_id)
            return False

        df = pd.DataFrame(
            [
                {
                    "ds": pd.to_datetime(transaction.transaction_date),
                    "y": float(transaction.amount),
                }
                for transaction in transactions
            ]
        )

        df = df.groupby("ds")["y"].sum().reset_index()
        series = df.set_index("ds")["y"].asfreq("D", fill_value=0.0)

        try:
            # TODO: Extract order and seasonal_order from ForecastingConfig or define in config
            self.forecaster_model = ForecastModels.train_sarima(
                train_data=series,
                order=(0, 1, 1),
                seasonal_order=(0, 1, 1, 4)
            )

            joblib.dump(self.forecaster_model, FORECASTER_MODEL_PATH)
            self._is_forecaster_loaded = True
            
            logger.info("Forecasting model trained successfully for user %s", user_id)
            return True

        except Exception as error:
            logger.error("Forecast training failed: %s", error)
            return False

    def get_forecast_predictions(
        self,
        db: Session,
        user_id: UUID,
        horizon: int,
    ) -> list[float]:
        if not self._is_forecaster_loaded or self.forecaster_model is None:
            logger.warning("Forecast model is not loaded.")
            return []

        logger.info("Generating forecast for user %s for %d periods", user_id, horizon)

        forecast_series = self.forecaster_model.forecast(steps=horizon)
        predictions = forecast_series.tolist()

        return predictions

    def get_user_seasonality(self, user_id: UUID) -> dict | None:
        if not self._is_forecaster_loaded or self.forecaster_model is None:
            logger.warning("Seasonality requested but model is not loaded.")
            return None

        try:
            underlying_model = self.forecaster_model.model
            return {
                "order": underlying_model.order,
                "seasonal_order": underlying_model.seasonal_order,
                "seasonal_period": underlying_model.seasonal_order[-1] if underlying_model.seasonal_order else None,
            }
        except (AttributeError, ValueError, TypeError) as error:
            logger.error("Failed to extract seasonality: %s", error)
            return None

ml_service = MLService()