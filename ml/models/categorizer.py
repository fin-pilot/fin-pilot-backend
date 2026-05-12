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
    def __init__(self, config: MLSettings):
        self.config = config

        tfidf_cfg = config.tfidf
        svm_cfg = config.svm

        logger.info("Initializing transaction categorizer.")

        self.pipeline = Pipeline(
            [
                (
                    "tfidf",
                    TfidfVectorizer(
                        analyzer=(tfidf_cfg.analyzer),
                        ngram_range=(tfidf_cfg.ngram_range),
                        min_df=tfidf_cfg.min_df,
                        max_df=tfidf_cfg.max_df,
                    ),
                ),
                (
                    "clf",
                    LinearSVC(
                        class_weight=(svm_cfg.class_weight),
                        max_iter=(svm_cfg.max_iter),
                        random_state=(svm_cfg.random_state),
                    ),
                ),
            ]
        )

    def train(self, x_train, y_train):
        logger.info("Training model...")
        self.pipeline.fit(x_train, y_train)

    def save_model(self):
        model_path = Path(self.config.model.path)
        model_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("Saving model to %s", model_path)
        joblib.dump(self.pipeline, model_path)

    def load_model(self):
        model_path = Path(self.config.model.path)

        logger.info("Loading model from %s", model_path)
        self.pipeline = joblib.load(model_path)

    def predict(self, texts):
        cleaned_texts = [str(text).lower() for text in texts]

        return self.pipeline.predict(cleaned_texts)
