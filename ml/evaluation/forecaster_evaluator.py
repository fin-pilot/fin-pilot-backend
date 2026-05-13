import logging
import numpy as np
from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_squared_error,
    r2_score,
)
from shared.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def evaluate_forecaster_model(model, actual, forecast_steps: int) -> dict:
    logger.info("Evaluating forecasting model...")

    predictions = model.predict(forecast_steps)

    if len(predictions) == 0:
        logger.warning("No predictions returned from model.")

        return {
            "mae": None,
            "mse": None,
            "rmse": None,
            "mape": None,
            "r2_score": None,
        }

    y_true = actual.tail(forecast_steps).to_numpy()
    y_pred = np.array(predictions)

    mae = mean_absolute_error(y_true, y_pred)
    mse = mean_squared_error(y_true, y_pred)
    rmse = np.sqrt(mse)
    mape = mean_absolute_percentage_error(y_true, y_pred)
    r2 = r2_score(y_true, y_pred)

    logger.info("MAE      : %.4f", mae)
    logger.info("MSE      : %.4f", mse)
    logger.info("RMSE     : %.4f", rmse)
    logger.info("MAPE     : %.4f", mape)
    logger.info("R2 Score : %.4f", r2)

    return {
        "mae": float(mae),
        "mse": float(mse),
        "rmse": float(rmse),
        "mape": float(mape),
        "r2_score": float(r2),
    }
