"""Train ExpenseForecaster from a CSV and persist to app/ml/models/sarima_forecaster.pkl."""

from __future__ import annotations

import argparse
import logging
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ml.expense_forecaster import ExpenseForecaster

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)


def _monthly_to_daily(df: pd.DataFrame, date_col: str, amount_col: str) -> pd.DataFrame:
    """Spread each month's total equally across calendar days in that month."""
    rows = []
    for _, r in df.iterrows():
        ts = pd.Timestamp(r[date_col])
        start = ts.replace(day=1).normalize()
        end = start + pd.offsets.MonthEnd(0)
        days = (end - start).days + 1
        per_day = float(r[amount_col]) / max(days, 1)
        for d in pd.date_range(start, end, freq="D"):
            rows.append({"date": d, "amount": per_day})
    return pd.DataFrame(rows)


def load_training_frame(path: str) -> pd.DataFrame:
    path_lower = path.lower()
    if path_lower.endswith(".csv"):
        df = pd.read_csv(path)
    elif path_lower.endswith(".parquet"):
        df = pd.read_parquet(path)
    else:
        raise ValueError("Unsupported file type (use .csv or .parquet)")

    date_col = None
    for c in ("date", "ds", "transaction_date"):
        if c in df.columns:
            date_col = c
            break
    if date_col is None:
        raise ValueError(f"No date column found. Columns: {list(df.columns)}")

    amount_col = None
    for c in ("amount", "y", "daily_total", "monthly_expense_total"):
        if c in df.columns:
            amount_col = c
            break
    if amount_col is None:
        raise ValueError(f"No amount column found. Columns: {list(df.columns)}")

    is_monthly_total = amount_col == "monthly_expense_total"

    df = df[[date_col, amount_col]].dropna()
    df = df.rename(columns={date_col: "date", amount_col: "amount"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)

    if is_monthly_total:
        logger.info("Converting monthly totals to synthetic daily amounts.")
        df = _monthly_to_daily(df, "date", "amount")
    else:
        daily = (
            df.groupby(df["date"].dt.normalize())["amount"]
            .sum()
            .reset_index()
        )
        daily.columns = ["date", "amount"]
        df = daily

    return df.sort_values("date")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train SARIMA expense forecaster.")
    parser.add_argument(
        "data_path",
        nargs="?",
        default=os.path.join(
            os.path.dirname(__file__), "..", "data", "personal_finance_tracker_dataset.csv"
        ),
        help="CSV or Parquet with date + amount (or monthly_expense_total).",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.data_path):
        logger.error("Data file not found: %s", args.data_path)
        sys.exit(1)

    df = load_training_frame(args.data_path)
    if len(df) < 14:
        logger.error("Need at least ~14 daily points after aggregation.")
        sys.exit(1)

    forecaster = ExpenseForecaster(verbose=True)
    forecaster.train(df, date_col="date", amount_col="amount")
    logger.info("Model saved to %s", forecaster.model_path)


if __name__ == "__main__":
    main()
