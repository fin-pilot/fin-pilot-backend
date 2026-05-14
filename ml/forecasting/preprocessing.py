import logging
from typing import Literal

import numpy as np
import pandas as pd

from backend.app.db.models import TransactionType
from shared.logging import setup_logging

setup_logging()

logger = logging.getLogger(__name__)


class ForecastPreprocessor:
    def clean_transactions(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        df = df.drop_duplicates()

        df = df.sort_values(by="transaction_date").reset_index(drop=True)

        return df

    def remove_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or len(df) < 10:
            return df

        q1 = df["y"].quantile(0.25)
        q3 = df["y"].quantile(0.75)

        iqr = q3 - q1

        lower_bound = max(0.0, q1 - 1.5 * iqr)

        upper_bound = q3 + 3.0 * iqr

        filtered_df = df[
            (df["y"] >= lower_bound) & (df["y"] <= upper_bound)
        ].copy()

        logger.info("Removed %s outliers.", len(df) - len(filtered_df))

        return filtered_df

    def aggregate_daily_expenses(self, df: pd.DataFrame) -> pd.DataFrame:
        expenses = df[
            df["transaction_type"] == TransactionType.EXPENSE.value
        ].copy()

        if expenses.empty:
            return pd.DataFrame(columns=["ds", "y"])

        expenses["ds"] = pd.to_datetime(expenses["transaction_date"])

        weekly = (
            expenses.set_index("ds")
            .resample("W")["amount"]
            .sum()
            .clip(lower=0)
            .to_frame(name="y")
        )

        weekly["y"] = weekly["y"].rolling(window=3, min_periods=1).mean()

        weekly = weekly.reset_index()

        return weekly

    def create_balance_series(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=["ds", "y"])

        df["ds"] = df["transaction_date"].dt.normalize()

        df["net_amount"] = np.where(
            df["transaction_type"] == TransactionType.INCOME.value,
            df["amount"],
            -df["amount"],
        )

        daily_net = df.groupby("ds")["net_amount"].sum().reset_index()

        daily_net.set_index("ds", inplace=True)

        idx = pd.date_range(
            start=daily_net.index.min(), end=daily_net.index.max(), freq="D"
        )

        daily_net = daily_net.reindex(idx, fill_value=0.0)

        balance = daily_net["net_amount"].cumsum().reset_index()

        balance.rename(
            columns={"index": "ds", "net_amount": "y"},
            inplace=True,
        )

        return balance

    def prepare_series(
        self,
        df: pd.DataFrame,
        target: Literal["expense", "balance"] = "expense",
    ) -> pd.DataFrame:
        df = self.clean_transactions(df)

        if target == "expense":
            series_df = self.aggregate_daily_expenses(df)

            return self.remove_outliers(series_df)

        if target == "balance":
            return self.create_balance_series(df)

        raise ValueError(f"Unknown forecasting target: {target}")
