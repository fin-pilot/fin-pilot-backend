import logging
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
import pmdarima as pm
from pmdarima.arima import ARIMA
from statsmodels.tsa.stattools import adfuller

from shared.config import MLSettings
from shared.logging import setup_logging

setup_logging()

logger = logging.getLogger(__name__)


class TransactionForecaster:
    def __init__(self, config: MLSettings) -> None:
        self.config = config
        self.sarima_config = self.config.forecaster.sarima

        self.model: ARIMA | None = None

    def fit(self, series: pd.Series) -> None:
        logger.info("Starting SARIMA parameter search...")

        prepared_series = self._prepare_series(series)

        if len(prepared_series) < 14:
            raise ValueError(
                f"Minimum 14 observations required, got {len(prepared_series)}."
            )

        if prepared_series.nunique() <= 1:
            raise ValueError(
                "Series is constant. SARIMA cannot be trained on constant data."
            )

        seasonal_enabled = self.sarima_config.seasonal
        seasonal_period = self.sarima_config.seasonal_period

        min_required = seasonal_period * 2

        if seasonal_enabled and len(prepared_series) < min_required:
            logger.warning(
                (
                    "Series too short for seasonal SARIMA "
                    "(len=%s, required=%s). "
                    "Falling back to non-seasonal ARIMA."
                ),
                len(prepared_series),
                min_required,
            )

            seasonal_enabled = False
            seasonal_period = 0

        try:
            self.model = pm.auto_arima(
                prepared_series,
                seasonal=seasonal_enabled,
                m=seasonal_period if seasonal_enabled else 1,
                start_p=0,
                start_q=0,
                max_p=self.sarima_config.max_p,
                max_q=self.sarima_config.max_q,
                max_d=self.sarima_config.max_d,
                start_P=0,
                start_Q=0,
                max_P=self.sarima_config.max_P,
                max_Q=self.sarima_config.max_Q,
                max_D=self.sarima_config.max_D,
                max_order=self.sarima_config.max_order,
                stepwise=self.sarima_config.stepwise,
                trace=self.sarima_config.trace,
                error_action=self.sarima_config.error_action,
                suppress_warnings=self.sarima_config.suppress_warnings,
                information_criterion=(
                    self.sarima_config.information_criterion
                ),
                with_intercept="auto",
                stationary=False,
                n_jobs=self.sarima_config.n_jobs,
            )

        except ValueError as error:
            logger.warning(
                "SARIMA fitting failed (%s). "
                "Retrying with simpler non-seasonal ARIMA.",
                error,
            )

            self.model = pm.auto_arima(
                prepared_series,
                seasonal=False,
                m=1,
                start_p=0,
                start_q=0,
                max_p=self.sarima_config.max_p,
                max_q=self.sarima_config.max_q,
                max_d=self.sarima_config.max_d,
                max_order=self.sarima_config.max_order,
                stepwise=self.sarima_config.stepwise,
                trace=self.sarima_config.trace,
                error_action=self.sarima_config.error_action,
                suppress_warnings=self.sarima_config.suppress_warnings,
                with_intercept="auto",
                stationary=False,
                n_jobs=self.sarima_config.n_jobs,
            )

        if self.model is None:
            raise ValueError("SARIMA model fitting failed.")

        logger.info(
            "Model fitted successfully. Order=%s Seasonal=%s",
            self.model.order,
            self.model.seasonal_order,
        )

    def update(self, new_series: pd.Series) -> None:
        if self.model is None:
            raise ValueError("Model is not initialized.")

        logger.info("Updating forecasting model...")

        prepared_series = self._prepare_series(new_series)

        self.model.update(prepared_series)

    def forecast(self, steps: int = 30) -> pd.DataFrame:
        if self.model is None:
            raise ValueError("Model is not initialized.")

        forecast_vals, conf_int = self.model.predict(
            n_periods=steps, return_conf_int=True
        )

        return pd.DataFrame(
            {
                "predicted_y": forecast_vals.astype(float),
                "conf_lower": conf_int[:, 0].astype(float),
                "conf_upper": conf_int[:, 1].astype(float),
            }
        )

    def save_model(self) -> None:
        model_path = self._model_path

        model_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("Saving forecasting model to %s", model_path)

        joblib.dump(self.model, model_path)

    def load_model(self) -> None:
        model_path = self._model_path

        if not model_path.exists():
            logger.warning("Forecasting model not found: %s", model_path)
            return

        logger.info("Loading forecasting model from %s", model_path)

        self.model = joblib.load(model_path)

    def check_stationarity(self, series: pd.Series) -> bool:
        prepared_series = self._prepare_series(series)

        if len(prepared_series) < 15:
            return True

        result: tuple[Any, ...] = adfuller(prepared_series.dropna())

        p_value = float(result[1])

        is_stationary = bool(p_value < 0.05)

        logger.info("ADF p-value: %.4f", p_value)
        logger.info("Stationary: %s", is_stationary)

        return is_stationary

    def _prepare_series(self, series: pd.Series) -> pd.Series:
        prepared = series.copy()

        prepared.index = pd.to_datetime(prepared.index)

        prepared = prepared.sort_index()

        prepared = prepared.astype(float)

        prepared = prepared.fillna(0.0)

        return prepared

    @property
    def _model_path(self) -> Path:
        return Path(self.config.forecaster.model.path)
