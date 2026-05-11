import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX
import warnings
from app.ml.logger import logger

warnings.filterwarnings("ignore")


class ExpenseForecaster:
    def __init__(self):
        self.model = None
        self.model_fit = None

    def prepare_data(
        self,
        df: pd.DataFrame,
        date_col: str = "date",
        amount_col: str = "amount",
    ) -> pd.Series:
        df[date_col] = pd.to_datetime(df[date_col])
        daily_series = df.groupby(df[date_col].dt.date)[amount_col].sum()
        daily_series.index = pd.to_datetime(daily_series.index)

        idx = pd.date_range(daily_series.index.min(), daily_series.index.max())
        return daily_series.reindex(idx, fill_value=0)

    def train(
        self,
        time_series: pd.Series,
        order=(1, 1, 1),
        seasonal_order=(1, 1, 1, 7),
    ):
        self.model = SARIMAX(
            time_series,
            order=order,
            seasonal_order=seasonal_order,
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        self.model_fit = self.model.fit(disp=False)

    def forecast(self, steps: int = 30) -> pd.Series:
        if self.model_fit is None:
            raise ValueError("Model is not trained.")

        return self.model_fit.forecast(steps=steps)
