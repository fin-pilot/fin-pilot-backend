import os
import pandas as pd
import joblib
import logging
from statsmodels.tsa.statespace.sarimax import SARIMAX
from pmdarima import auto_arima
from uuid import UUID

logger = logging.getLogger(__name__)


class ExpenseForecaster:
    def __init__(self, models_dir: str = "ml/saved_models"):
        self.models_dir = models_dir
        self.base_model_path = os.path.join(models_dir, "base_sarima.pkl")
        if not os.path.exists(self.models_dir):
            os.makedirs(self.models_dir)

    def _get_user_path(self, user_id: UUID) -> str:
        return os.path.join(self.models_dir, f"forecaster_{user_id}.pkl")

    def preprocess(self, transactions: list) -> pd.Series:
        if not transactions:
            return pd.Series(dtype=float)

        df = pd.DataFrame(
            [
                {"date": t.transaction_date, "amount": t.amount}
                for t in transactions
            ]
        )
        df["date"] = pd.to_datetime(df["date"])
        series = df.set_index("date")["amount"].resample("D").sum().fillna(0)
        return series

    def train_user_model(self, user_id: UUID, series: pd.Series):
        logger.info(f"Training full SARIMA for user {user_id}...")

        stepwise_model = auto_arima(
            series, seasonal=True, m=7, suppress_warnings=True
        )

        model = SARIMAX(
            series,
            order=stepwise_model.order,
            seasonal_order=stepwise_model.seasonal_order,
            enforce_stationarity=False,
        )
        result = model.fit(disp=False)

        joblib.dump(result, self._get_user_path(user_id))
        return result

    def get_forecast(
        self, user_id: UUID, fresh_transactions: list, steps: int = 30
    ):
        user_path = self._get_user_path(user_id)

        if os.path.exists(user_path):
            result = joblib.load(user_path)
        elif os.path.exists(self.base_model_path):
            result = joblib.load(self.base_model_path)
        else:
            return {"error": "Base model not found. Initial training required."}

        if fresh_transactions:
            fresh_series = self.preprocess(fresh_transactions)
            result = result.extend(fresh_series)
            joblib.dump(result, user_path)

        forecast = result.get_forecast(steps=steps)
        return {
            "predicted_mean": forecast.predicted_mean.to_dict(),
            "last_date": result.model.data.orig_endog.index[-1].isoformat(),
        }
