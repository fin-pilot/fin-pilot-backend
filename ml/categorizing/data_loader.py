import logging
from typing import cast

import pandas as pd
from datasets import load_dataset

from shared.config import (
    backend_settings,
    ml_settings,
)
from shared.logging import setup_logging

setup_logging()

logger = logging.getLogger(__name__)


class CategorizerDataLoader:
    def __init__(self) -> None:
        self.dataset_name = ml_settings.dataset.categorizer.name

    def load(self):
        logger.info("Loading dataset: %s", self.dataset_name)

        dataset = load_dataset(
            self.dataset_name, token=backend_settings.HF_TOKEN
        )

        df = cast(pd.DataFrame, dataset["train"].to_pandas())
        df = df.dropna(subset=["transaction_description", "category"])
        df["description"] = (
            df["transaction_description"].astype(str).str.lower()
        )

        logger.info("Loaded %s cleaned samples.", len(df))

        return (df["description"], df["category"])
