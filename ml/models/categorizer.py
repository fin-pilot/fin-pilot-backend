import logging
from pathlib import Path
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
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

        base_svm = LinearSVC(
            class_weight=(svm_cfg.class_weight),
            max_iter=(svm_cfg.max_iter),
            random_state=(svm_cfg.random_state),
        )

        calibrated_svm = CalibratedClassifierCV(
            base_svm, cv=5, method="sigmoid"
        )

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
                    calibrated_svm,
                ),
            ]
        )

    def train(self, x_train, y_train):
        logger.info("Training model with probability calibration...")
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

    def predict(self, texts: list[str]) -> list[str]:
        cleaned_texts = [str(text).lower() for text in texts]
        return self.pipeline.predict(cleaned_texts)

    def predict_with_confidence(self, description: str) -> tuple[str, float]:
        if self.pipeline is None:
            logger.warning("Pipeline is not loaded. Cannot predict.")
            return "Uncategorized", 0.0

        cleaned_text = str(description).lower()

        try:
            probabilities = self.pipeline.predict_proba([cleaned_text])[0]

            max_prob = max(probabilities)

            best_class_index = probabilities.argmax()
            predicted_label = self.pipeline.classes_[best_class_index]

            return str(predicted_label), float(max_prob)
        except AttributeError:
            logger.warning(
                "Model does not support predict_proba. "
                "Returning label with default 0.99 confidence. Please retrain."
            )
            prediction = self.pipeline.predict([cleaned_text])[0]
            return str(prediction), 0.99
