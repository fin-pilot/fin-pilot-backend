# app/ml/expense_forecaster.py

import os
import logging
import joblib
import numpy as np
import pandas as pd

from dataclasses import dataclass
from statsmodels.tsa.statespace.sarimax import SARIMAX
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
)

# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# =========================================================
# DTO
# =========================================================


@dataclass
class ForecastResult:
    predictions: list
    confidence_lower: list
    confidence_upper: list


# =========================================================
# FORECASTER
# =========================================================


class ExpenseForecaster:
    def __init__(
        self,
        model_path="app/ml/models/sarima_forecaster.pkl",
        order=(1, 1, 1),
        seasonal_order=(1, 1, 1, 30),
        verbose: bool = True,
    ):
        base_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )

        self.model_path = os.path.join(base_dir, model_path)

        self.order = order
        self.seasonal_order = seasonal_order

        self.model = None
        self.series = None

        self.verbose = verbose

    # =====================================================
    # LOGGING
    # =====================================================

    def _log(self, message: str):
        if self.verbose:
            logger.info(message)

    # =====================================================
    # DATA PREPARATION
    # =====================================================

    def _prepare_series(
        self,
        df: pd.DataFrame,
        date_col: str,
        amount_col: str,
    ) -> pd.Series:
        self._log("Preparing time series data...")

        data = df.copy()

        data[date_col] = pd.to_datetime(
            data[date_col],
            errors="coerce",
        )

        data = data.dropna(subset=[date_col, amount_col])

        daily = (
            data.groupby(data[date_col].dt.date)[amount_col].sum().reset_index()
        )

        daily.columns = ["date", "amount"]

        daily["date"] = pd.to_datetime(daily["date"])

        daily = daily.sort_values("date")

        daily = daily.set_index("date")

        daily = daily.asfreq("D", fill_value=0)

        self._log(f"Prepared {len(daily)} daily observations.")

        return daily["amount"]

    # =====================================================
    # MODEL BUILDING
    # =====================================================

    def build_model(self):
        self._log("Building SARIMA model...")

        self.model = SARIMAX(
            self.series,
            order=self.order,
            seasonal_order=self.seasonal_order,
            enforce_stationarity=False,
            enforce_invertibility=False,
        )

    # =====================================================
    # TRAINING
    # =====================================================

    def train(
        self,
        df: pd.DataFrame,
        date_col: str = "date",
        amount_col: str = "amount",
    ):
        self._log("Starting forecasting training pipeline...")

        initial_size = len(df)

        df = df.dropna(subset=[date_col, amount_col])

        self._log(f"Removed {initial_size - len(df)} rows with missing values.")

        self.series = self._prepare_series(
            df=df,
            date_col=date_col,
            amount_col=amount_col,
        )

        self._log(f"Time series length: {len(self.series)}")

        self.build_model()

        self._log("Training SARIMA model...")

        self.model = self.model.fit(disp=False)

        self._log("Training completed.")

        self.evaluate()

        self.save_model()

    # =====================================================
    # USER ADAPTATION
    # =====================================================

    def adapt_to_user(
        self,
        user_df: pd.DataFrame,
        date_col: str = "date",
        amount_col: str = "amount",
    ):
        if self.model is None or self.series is None:
            self._log("Loading pretrained model...")
            self.load_model()

        self._log("Adapting forecasting model to user data...")

        user_series = self._prepare_series(
            user_df,
            date_col=date_col,
            amount_col=amount_col,
        )

        combined = pd.concat([self.series, user_series])

        combined = combined.groupby(combined.index).sum()

        self.series = combined.sort_index()

        self.build_model()

        self.model = self.model.fit(disp=False)

        self._log("User adaptation completed.")

    # =====================================================
    # FORECASTING
    # =====================================================

    def forecast(self, steps: int = 30) -> ForecastResult:
        if self.model is None:
            self._log("Loading forecasting model...")
            self.load_model()

        self._log(f"Generating forecast for {steps} days...")

        forecast_obj = self.model.get_forecast(steps=steps)

        predicted_mean = forecast_obj.predicted_mean

        confidence = forecast_obj.conf_int()

        return ForecastResult(
            predictions=predicted_mean.tolist(),
            confidence_lower=confidence.iloc[:, 0].tolist(),
            confidence_upper=confidence.iloc[:, 1].tolist(),
        )

    # =====================================================
    # EVALUATION
    # =====================================================

    def evaluate(self, test_size: int = 30):
        self._log("Evaluating forecasting model...")

        train = self.series[:-test_size]
        test = self.series[-test_size:]

        eval_model = SARIMAX(
            train,
            order=self.order,
            seasonal_order=self.seasonal_order,
            enforce_stationarity=False,
            enforce_invertibility=False,
        ).fit(disp=False)

        predictions = eval_model.forecast(test_size)

        mae = mean_absolute_error(test, predictions)

        rmse = np.sqrt(mean_squared_error(test, predictions))

        # =====================================================
        # sMAPE (SAFE FOR NEGATIVE / ZERO VALUES)
        # =====================================================

        denominator = (np.abs(test) + np.abs(predictions)) / 2

        denominator = np.where(
            denominator == 0,
            1e-10,
            denominator,
        )

        smape = np.mean(np.abs(test - predictions) / denominator) * 100

        self._log(f"MAE   : {mae:.4f}")
        self._log(f"RMSE  : {rmse:.4f}")
        self._log(f"sMAPE : {smape:.2f}%")

        return {
            "MAE": mae,
            "RMSE": rmse,
            "sMAPE": smape,
        }

    # =====================================================
    # ANOMALY DETECTION
    # =====================================================

    def detect_overspending(
        self,
        user_df: pd.DataFrame,
        date_col="date",
        amount_col="amount",
        window=30,
        threshold=2.0,
    ):
        self._log("Detecting overspending anomalies...")

        series = self._prepare_series(
            user_df,
            date_col=date_col,
            amount_col=amount_col,
        )

        rolling_mean = series.rolling(window).mean()

        rolling_std = series.rolling(window).std()

        anomalies = series[series > rolling_mean + threshold * rolling_std]

        self._log(f"Detected {len(anomalies)} anomalies.")

        return anomalies

    # =====================================================
    # MODEL PERSISTENCE
    # =====================================================

    def save_model(self):
        os.makedirs(
            os.path.dirname(self.model_path),
            exist_ok=True,
        )

        joblib.dump(
            {
                "model": self.model,
                "series": self.series,
                "order": self.order,
                "seasonal_order": self.seasonal_order,
            },
            self.model_path,
        )

        self._log(f"Forecasting model saved to: {self.model_path}")

    def load_model(self):
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(
                f"Forecasting model not found: {self.model_path}"
            )

        data = joblib.load(self.model_path)

        self.model = data["model"]
        self.series = data["series"]

        self.order = data["order"]
        self.seasonal_order = data["seasonal_order"]

        self._log("Forecasting model loaded successfully.")
