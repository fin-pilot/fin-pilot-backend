import logging
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from shared.config import MLSettings
from shared.logging.config import setup_logging

setup_logging()

logger = logging.getLogger(__name__)


class TransactionCategorizer:
    def __init__(self, config: MLSettings) -> None:
        self.config = config

        logger.info("Initializing transaction categorizer.")

        self.pipeline = self._build_pipeline()

    def train(self, x_train: list[str], y_train: list[str]) -> None:
        logger.info("Training transaction categorizer...")

        cleaned_texts = self._clean_texts(x_train)

        self.pipeline.fit(cleaned_texts, y_train)

    def predict(self, texts: list[str]) -> list[str]:
        cleaned_texts = self._clean_texts(texts)

        predictions = self.pipeline.predict(cleaned_texts)

        return [str(prediction) for prediction in predictions]

    def save_model(self) -> None:
        model_path = self._model_path

        model_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("Saving model to %s", model_path)

        joblib.dump(self.pipeline, model_path)

    def load_model(self) -> None:
        model_path = self._model_path

        if not model_path.exists():
            logger.warning("Model file not found: %s", model_path)
            return

        logger.info("Loading model from %s", model_path)

        self.pipeline = joblib.load(model_path)

    @property
    def _model_path(self) -> Path:
        return Path(self.config.categorizer.model.path)

    def _build_pipeline(self) -> Pipeline:
        return Pipeline(
            [
                ("tfidf", self._create_vectorizer()),
                ("clf", self._create_classifier()),
            ]
        )

    def _create_vectorizer(self) -> TfidfVectorizer:
        cfg = self.config.categorizer.tfidf

        return TfidfVectorizer(
            analyzer=cfg.analyzer,
            ngram_range=cfg.ngram_range,
            min_df=cfg.min_df,
            max_df=cfg.max_df,
        )

    def _create_classifier(self) -> LinearSVC:
        cfg = self.config.categorizer.svm

        return LinearSVC(
            class_weight=cfg.class_weight,
            max_iter=cfg.max_iter,
            random_state=cfg.random_state,
        )

    @staticmethod
    def _clean_texts(texts: list[str]) -> list[str]:
        return [str(text).lower() for text in texts]
