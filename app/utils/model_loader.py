"""Model artifact download utilities.

Downloads pre-trained model files from the fin-pilot-ml GitHub repository if
they are not already present on disk.  Failures are logged as warnings so that
the application starts in cold-start mode rather than crashing.
"""

from __future__ import annotations

import logging
from pathlib import Path
from urllib.request import urlretrieve
from urllib.error import URLError

logger = logging.getLogger(__name__)

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

CATEGORIZER_MODEL_PATH = Path("artifacts/categorizing/models/model.pkl")
FORECASTER_MODEL_PATH = Path("artifacts/forecasting/models/sarima.pkl")


def _download_file(url: str, destination: Path) -> bool:
    """Download *url* to *destination*.  Returns True on success."""
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Downloading model artifact from %s …", url)
        urlretrieve(url, destination)
        logger.info("Model artifact saved to %s.", destination)
        return True
    except URLError as exc:
        logger.warning(
            "Could not download model from %s (network error: %s). "
            "Starting in cold-start mode for this component.",
            url,
            exc,
        )
    except OSError as exc:
        logger.warning(
            "Could not save model to %s (%s). "
            "Starting in cold-start mode for this component.",
            destination,
            exc,
        )
    return False


def download_categorizer_model_if_needed() -> None:
    if CATEGORIZER_MODEL_PATH.exists():
        return
    _download_file(CATEGORIZER_MODEL_URL, CATEGORIZER_MODEL_PATH)


def download_forecaster_model_if_needed() -> None:
    if FORECASTER_MODEL_PATH.exists():
        return
    _download_file(FORECASTER_MODEL_URL, FORECASTER_MODEL_PATH)
