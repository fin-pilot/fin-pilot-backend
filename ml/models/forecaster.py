import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pmdarima as pm
from numpy.linalg import LinAlgError

from shared.config import MLSettings
from shared.logging.config import setup_logging
import shared.config.ml

setup_logging()
logger = logging.getLogger(__name__)


class ExpenseForecaster:
    def __init__(self, config: MLSettings) -> None:
        self.config = config

        self.sarima_cfg = config.forecaster.sarima

        logger.info("Initializing expense forecaster.")

        self.model = None

    def preprocess(
        self,
        df: pd.DataFrame,
    ) -> pd.Series:
        if df.empty:
            return pd.Series(dtype=float)

        prepared_df = self._prepare_dataframe(df)

        return self._build_time_series(prepared_df)

    def train(
        self,
        df: pd.DataFrame,
    ) -> bool:
        logger.info("Training SARIMA model...")

        ts = self.preprocess(df)

        if not self._has_enough_data(ts):
            logger.warning(
                "Not enough data to fit " "SARIMA. Need at least %d periods.",
                2 * self.sarima_cfg.seasonal_period,
            )

            return False

        try:
            self.model = self._create_model(ts)

            logger.info("SARIMA model trained successfully.")

            return True

        except (
            ValueError,
            TypeError,
            LinAlgError,
        ) as error:
            logger.error(
                "Failed to train SARIMA model: %s",
                error,
            )

            return False

    def update(
        self,
        df: pd.DataFrame,
    ) -> bool:
        if self.model is None:
            logger.warning("Cannot update: model is not loaded.")

            return False

        ts = self.preprocess(df)

        if ts.empty:
            logger.info("No new data to update model.")

            return True

        try:
            self.model.update(ts)

            logger.info("SARIMA model updated successfully.")

            return True

        except (
            ValueError,
            TypeError,
            LinAlgError,
        ) as error:
            logger.error(
                "Failed to update SARIMA model: %s",
                error,
            )

            return False

    def predict(
        self,
        steps: int,
    ) -> list[float]:
        if self.model is None:
            logger.warning("Cannot predict: model is not loaded.")

            return []

        try:
            forecast = self.model.predict(n_periods=steps)

            return self._format_forecast(forecast)

        except (
            ValueError,
            TypeError,
            LinAlgError,
        ) as error:
            logger.error(
                "Prediction failed: %s",
                error,
            )

            return []

    def save_model(self) -> None:
        if self.model is None:
            logger.warning("Cannot save: model is empty.")

            return

        model_path = self._get_model_path()

        model_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        logger.info(
            "Saving model to %s",
            model_path,
        )

        joblib.dump(
            self.model,
            model_path,
        )

    def load_model(self) -> None:
        model_path = self._get_model_path()

        if not model_path.exists():
            logger.warning(
                "Model file not found: %s",
                model_path,
            )

            self.model = None

            return

        logger.info(
            "Loading model from %s",
            model_path,
        )

        self.model = joblib.load(model_path)

    def _prepare_dataframe(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        prepared_df = df.copy()

        prepared_df["date"] = pd.to_datetime(prepared_df["date"])

        prepared_df["amount"] = prepared_df["amount"].abs()

        prepared_df.set_index(
            "date",
            inplace=True,
        )

        return prepared_df

    def _build_time_series(
        self,
        df: pd.DataFrame,
    ) -> pd.Series:
        return df["amount"].resample(self.sarima_cfg.freq).sum().fillna(0.0)

    def _has_enough_data(
        self,
        ts: pd.Series,
    ) -> bool:
        minimum_periods = 2 * self.sarima_cfg.seasonal_period

        return len(ts) >= minimum_periods

    def _create_model(
        self,
        ts: pd.Series,
    ):
        return pm.auto_arima(
            ts,
            seasonal=self.sarima_cfg.seasonal,
            m=self.sarima_cfg.seasonal_period,
            stepwise=self.sarima_cfg.stepwise,
            trace=self.sarima_cfg.trace,
            error_action=self.sarima_cfg.error_action,
            suppress_warnings=(self.sarima_cfg.suppress_warnings),
        )

    def _format_forecast(
        self,
        forecast: np.ndarray,
    ) -> list[float]:
        return np.round(
            forecast.tolist(),
            2,
        ).tolist()

    def _get_model_path(self) -> Path:
        return Path(self.config.forecaster.model.path)
