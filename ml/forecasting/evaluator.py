import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
)

from shared.logging import setup_logging

setup_logging()

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ForecastMetrics:
    mae: float
    rmse: float
    wape: float


class ForecastEvaluator:
    def evaluate(
        self, y_true: np.ndarray, y_pred: np.ndarray
    ) -> ForecastMetrics:
        logger.info("Evaluating forecasting model...")

        mae = float(mean_absolute_error(y_true, y_pred))
        rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
        total_actual = np.sum(np.abs(y_true))

        if total_actual == 0:
            wape = 0.0
        else:
            wape = float(np.sum(np.abs(y_true - y_pred)) / total_actual)

        logger.info("MAE  : %.4f", mae)
        logger.info("RMSE : %.4f", rmse)
        logger.info("WAPE : %.4f", wape)

        return ForecastMetrics(mae=mae, rmse=rmse, wape=wape)

    def evaluate_walk_forward(
        self,
        model,
        series: pd.Series,
        initial_train_size: int = 52,
        step: int = 4,
    ) -> ForecastMetrics:
        logger.info("Starting walk-forward validation...")

        if len(series) <= initial_train_size:
            logger.warning("Series too short for validation.")

            return ForecastMetrics(mae=0.0, rmse=0.0, wape=0.0)

        all_true = []
        all_pred = []

        for i in range(initial_train_size, len(series), step):
            train_split = series.iloc[:i]

            test_split = series.iloc[i : i + step]

            try:
                temp_model = model.__class__(model.config)

                temp_model.fit(train_split)

                forecast_df = temp_model.forecast(steps=len(test_split))

                all_true.extend(test_split.values)

                all_pred.extend(forecast_df["predicted_y"].values)

            except Exception as error:
                logger.error("Walk-forward failed at step %s: %s", i, error)

        if not all_true or not all_pred:
            logger.warning("No successful walk-forward predictions generated.")

            return ForecastMetrics(mae=0.0, rmse=0.0, wape=0.0)

        return self.evaluate(np.array(all_true), np.array(all_pred))
