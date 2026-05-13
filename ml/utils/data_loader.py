import logging
from pathlib import Path
from typing import cast
import kagglehub
import pandas as pd
from datasets import load_dataset

from shared.config import (
    backend_settings,
    ml_settings,
)
from shared.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def load_categorizer_data():
    dataset_name = ml_settings.dataset.categorizer.name

    logger.info("Loading dataset: %s", dataset_name)

    dataset = load_dataset(dataset_name, token=backend_settings.HF_TOKEN)

    df = cast(pd.DataFrame, dataset["train"].to_pandas())
    df = df.dropna(subset=["transaction_description", "category"])
    df["description"] = df["transaction_description"].astype(str).str.lower()

    logger.info("Loaded %s cleaned samples.", len(df))

    return (df["description"], df["category"])


def load_forecaster_data():
    dataset_identifier = ml_settings.dataset.forecaster.name

    logger.info(
        "Downloading dataset: %s...",
        dataset_identifier,
    )

    path = Path(kagglehub.dataset_download(dataset_identifier))

    logger.info("Dataset downloaded to: %s", path)

    csv_files = list(path.rglob("Expenses_clean.csv"))

    if not csv_files:
        logger.error("Expenses_clean.csv not found inside %s", path)
        return pd.DataFrame()

    csv_path = csv_files[0]

    logger.info("Loading expense data from %s...", csv_path)

    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

    logger.info("Detected columns: %s", df.columns.tolist())

    required_columns = ["date_time", "amount"]
    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        logger.error("Missing required columns: %s", missing_columns)
        return pd.DataFrame()

    forecast_df = pd.DataFrame(
        {
            "date": pd.to_datetime(df["date_time"], errors="coerce"),
            "amount": pd.to_numeric(df["amount"], errors="coerce"),
        }
    )

    forecast_df = forecast_df.dropna(subset=["date", "amount"])
    forecast_df = forecast_df.sort_values("date").reset_index(drop=True)

    logger.info("Successfully loaded %d expense records.", len(forecast_df))

    return forecast_df
