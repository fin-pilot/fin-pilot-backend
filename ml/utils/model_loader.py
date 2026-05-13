import logging
from pathlib import Path

import requests

from shared.config import ml_settings
from shared.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def download_categorizer_model_if_needed():
    model_path = Path(ml_settings.categorizer.model.path)

    model_url = ml_settings.categorizer.model.release_url

    _download_model_if_needed(
        model_path=model_path,
        model_url=model_url,
        model_name="categorizer",
    )


def download_forecaster_model_if_needed():
    model_path = Path(ml_settings.forecaster.model.path)

    model_url = ml_settings.forecaster.model.release_url

    _download_model_if_needed(
        model_path=model_path,
        model_url=model_url,
        model_name="forecaster",
    )


def _download_model_if_needed(
    model_path: Path,
    model_url: str | None,
    model_name: str,
) -> None:
    if model_path.exists():
        logger.info(
            "%s model already exists at %s",
            model_name,
            model_path,
        )

        return

    if not model_url:
        logger.warning(
            "No release_url provided for %s model.",
            model_name,
        )

        return

    logger.info(
        "Downloading %s model from %s...",
        model_name,
        model_url,
    )

    model_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        response = requests.get(
            model_url,
            stream=True,
            timeout=30,
        )

        response.raise_for_status()

        with open(
            model_path,
            "wb",
        ) as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)

        logger.info(
            "%s model downloaded successfully to %s",
            model_name,
            model_path,
        )

    except requests.RequestException as error:
        logger.error(
            "Failed to download %s model: %s",
            model_name,
            error,
        )

        raise
