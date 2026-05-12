import logging
from datasets import load_dataset
from shared.logging import setup_logging
from shared.config import backend_settings, ml_settings

setup_logging()
logger = logging.getLogger(__name__)


def load_transaction_data():
    logger.info("Loading dataset: %s", ml_settings.dataset.name)

    dataset = load_dataset(
        ml_settings.dataset.name, token=backend_settings.HF_TOKEN
    )

    df = dataset["train"].to_pandas()

    df = df.dropna(subset=["transaction_description", "category"])

    df["description"] = df["transaction_description"].astype(str).str.lower()

    logger.info("Loaded %s cleaned samples.", len(df))

    return (df["description"], df["category"])
