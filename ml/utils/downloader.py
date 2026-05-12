import logging
import requests
from pathlib import Path
from shared.config import ml_settings
from shared.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def download_model_if_needed():
    model_path = Path(ml_settings.model.path)
    url = ml_settings.model.release_url

    if model_path.exists():
        logger.info("ML model already exists at %s", model_path)
        return

    if not url:
        logger.warning("No release_url provided in config. Skipping download.")
        return

    logger.info("Downloading ML model from %s...", url)
    model_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        with open(model_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.info("Model successfully downloaded and saved to %s", model_path)
    except Exception as e:
        logger.error("Failed to download model: %s", str(e))
        raise
