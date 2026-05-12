from functools import lru_cache
from typing import Any

import yaml
from pydantic import BaseModel

from .paths import ML_CONFIG_FILE


class DatasetConfig(BaseModel):
    name: str


class DataConfig(BaseModel):
    test_size: float = 0.2
    random_state: int = 42


class ModelConfig(BaseModel):
    path: str


class TFIDFConfig(BaseModel):
    analyzer: str = "char_wb"

    ngram_range: tuple[int, int] = (2, 5)

    min_df: int = 5
    max_df: float = 0.5


class SVMConfig(BaseModel):
    class_weight: str = "balanced"

    max_iter: int = 2000

    random_state: int = 42


class MLSettings(BaseModel):
    dataset: DatasetConfig
    data: DataConfig
    model: ModelConfig
    tfidf: TFIDFConfig
    svm: SVMConfig


def _load_yaml_config() -> dict[str, Any]:
    if not ML_CONFIG_FILE.exists():
        raise FileNotFoundError(f"ML config not found: " f"{ML_CONFIG_FILE}")

    with open(
        ML_CONFIG_FILE,
        "r",
        encoding="utf-8",
    ) as file:
        data = yaml.safe_load(file)

    if data is None:
        raise ValueError("ML config file is empty.")

    return data


@lru_cache
def get_ml_settings() -> MLSettings:
    config_data = _load_yaml_config()

    return MLSettings(**config_data)


ml_settings = get_ml_settings()
