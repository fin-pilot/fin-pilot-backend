from pathlib import Path
from urllib.request import urlretrieve


CATEGORIZER_MODEL_URL = (
    "https://raw.githubusercontent.com/"
    "fin-pilot/fin-pilot-ml/main/"
    "artifacts/categorizing/models/model.pkl"
)

FORECASTER_MODEL_URL = (
    "https://raw.githubusercontent.com/"
    "fin-pilot/fin-pilot-ml/main/"
    "artifacts/forecasting/models/sarima.pkl"
)


CATEGORIZER_MODEL_PATH = Path(
    "artifacts/categorizing/models/model.pkl"
)

FORECASTER_MODEL_PATH = Path(
    "artifacts/forecasting/models/sarima.pkl"
)


def _download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)

    print(f"Downloading model from {url}")

    urlretrieve(url, destination)

    print(f"Saved model to {destination}")


def download_categorizer_model_if_needed() -> None:
    if CATEGORIZER_MODEL_PATH.exists():
        return

    _download_file(
        CATEGORIZER_MODEL_URL,
        CATEGORIZER_MODEL_PATH,
    )


def download_forecaster_model_if_needed() -> None:
    if FORECASTER_MODEL_PATH.exists():
        return

    _download_file(
        FORECASTER_MODEL_URL,
        FORECASTER_MODEL_PATH,
    )