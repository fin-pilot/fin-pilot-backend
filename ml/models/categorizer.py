import logging
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from shared.config import MLSettings
from shared.logging.config import setup_logging
import shared.config.ml
import sklearn.svm._classes

setup_logging()
logger = logging.getLogger(__name__)


class TransactionCategorizer:
    def __init__(self, config: MLSettings) -> None:
        self.config = config

        logger.info("Initializing transaction categorizer.")

        self.pipeline = self._create_pipeline()

    def train(
        self,
        x_train: list[str],
        y_train: list[str],
    ) -> None:
        logger.info("Training transaction categorizer...")

        cleaned_texts = self._clean_texts(x_train)

        self.pipeline.fit(
            cleaned_texts,
            y_train,
        )

    def predict(
        self,
        texts: list[str],
    ) -> list[str]:
        cleaned_texts = self._clean_texts(texts)

        predictions = self.pipeline.predict(cleaned_texts)

        return self._format_predictions(predictions)

    def save_model(self) -> None:
        model_path = self._get_model_path()

        model_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        logger.info(
            "Saving model to %s",
            model_path,
        )

        joblib.dump(
            self.pipeline,
            model_path,
        )

    def load_model(self) -> None:
        model_path = self._get_model_path()

        if not model_path.exists():
            logger.warning(
                "Model file not found: %s",
                model_path,
            )

            return

        logger.info(
            "Loading model from %s",
            model_path,
        )

        self.pipeline = joblib.load(model_path)

    def _create_pipeline(self) -> Pipeline:
        return Pipeline(
            [
                (
                    "tfidf",
                    self._create_vectorizer(),
                ),
                (
                    "clf",
                    self._create_classifier(),
                ),
            ]
        )

    def _create_vectorizer(
        self,
    ) -> TfidfVectorizer:
        tfidf_cfg = self.config.categorizer.tfidf

        return TfidfVectorizer(
            analyzer=tfidf_cfg.analyzer,
            ngram_range=tfidf_cfg.ngram_range,
            min_df=tfidf_cfg.min_df,
            max_df=tfidf_cfg.max_df,
        )

    def _create_classifier(
        self,
    ) -> LinearSVC:
        svm_cfg = self.config.categorizer.svm

        return LinearSVC(
            class_weight=svm_cfg.class_weight,
            max_iter=svm_cfg.max_iter,
            random_state=svm_cfg.random_state,
        )

    def _clean_texts(
        self,
        texts: list[str],
    ) -> list[str]:
        return [str(text).lower() for text in texts]

    def _format_predictions(
        self,
        predictions,
    ) -> list[str]:
        return [str(prediction) for prediction in predictions]

    def _get_model_path(self) -> Path:
        return Path(self.config.categorizer.model.path)
