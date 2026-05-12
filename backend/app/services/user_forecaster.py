"""Train SARIMA-style models on a user's daily expense history with sensible fallbacks."""

from __future__ import annotations

import logging
from typing import List, Tuple

import pandas as pd

from app.ml.expense_forecaster import ExpenseForecaster

logger = logging.getLogger(__name__)

MIN_HISTORY_DAYS = 7


def train_forecaster_for_history(
    df: pd.DataFrame,
) -> ExpenseForecaster:
    if df is None or len(df) < MIN_HISTORY_DAYS:
        raise ValueError(
            f"Need at least {MIN_HISTORY_DAYS} days with expense data to forecast."
        )

    configs: List[Tuple[tuple, tuple]] = [
        ((1, 1, 1), (1, 1, 1, 7)),
        ((1, 1, 1), (1, 1, 1, 30)),
        ((1, 1, 1), (0, 0, 0, 0)),
        ((0, 1, 1), (0, 0, 0, 0)),
    ]

    last_error: Exception | None = None
    for order, seasonal_order in configs:
        try:
            forecaster = ExpenseForecaster(
                order=order,
                seasonal_order=seasonal_order,
                verbose=False,
            )
            forecaster.train(df, date_col="date", amount_col="amount")
            return forecaster
        except Exception as exc:  # noqa: BLE001 — try next config
            last_error = exc
            logger.debug("Forecaster config failed: %s", exc)

    if last_error:
        raise ValueError("Could not fit expense forecaster.") from last_error
    raise ValueError("Could not fit expense forecaster.")
