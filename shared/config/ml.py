from functools import lru_cache
from typing import Any

import yaml
from pydantic import BaseModel

from .paths import ML_CONFIG_FILE


class CategorizerDatasetConfig(BaseModel):
    name: str


class ForecasterDatasetConfig(BaseModel):
    name: str


class DatasetConfig(BaseModel):
    categorizer: CategorizerDatasetConfig

    forecaster: ForecasterDatasetConfig


class DataConfig(BaseModel):
    test_size: float = 0.2

    random_state: int = 42


class CategorizerModelConfig(BaseModel):
    path: str

    release_url: str | None = None


class ForecasterModelConfig(BaseModel):
    path: str

    release_url: str | None = None


class CategorizerTFIDFConfig(BaseModel):
    analyzer: str = "char_wb"

    ngram_range: tuple[int, int] = (2, 5)

    min_df: int = 5

    max_df: float = 0.5


class CategorizerSVMConfig(BaseModel):
    class_weight: str = "balanced"

    max_iter: int = 2000

    random_state: int = 42


class SARIMAConfig(BaseModel):
    seasonal: bool = True

    seasonal_period: int = 12

    freq: str = "ME"

    stepwise: bool = True

    trace: bool = False

    error_action: str = "ignore"

    suppress_warnings: bool = True

    information_criterion: str = "aic"

    max_p: int = 5

    max_q: int = 5

    max_d: int = 2

    max_P: int = 2

    max_Q: int = 2

    max_D: int = 1


class CategorizerConfig(BaseModel):
    model: CategorizerModelConfig

    tfidf: CategorizerTFIDFConfig

    svm: CategorizerSVMConfig


class ForecasterConfig(BaseModel):
    model: ForecasterModelConfig

    sarima: SARIMAConfig


class MLSettings(BaseModel):
    dataset: DatasetConfig

    data: DataConfig

    categorizer: CategorizerConfig

    forecaster: ForecasterConfig


def _load_yaml_config() -> dict[str, Any]:
    if not ML_CONFIG_FILE.exists():
        raise FileNotFoundError(f"ML config not found: {ML_CONFIG_FILE}")

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
