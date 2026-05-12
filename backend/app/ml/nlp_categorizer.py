import pandas as pd
import joblib
import re
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


class TransactionCategorizer:
    def __init__(
        self,
        model_path="app/ml/models/svm_categorizer.pkl",
        verbose: bool = True,
    ):
        base_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )

        self.model_path = os.path.join(base_dir, model_path)
        self.pipeline = None
        self.verbose = verbose

    def _log(self, message: str):
        if self.verbose:
            logger.info(message)

    def _clean_text(self, text: str) -> str:
        if not isinstance(text, str):
            return ""

        text = text.lower()
        text = re.sub(r"\d+", "", text)
        text = re.sub(r"[^\w\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        return text

    def build_pipeline(self):
        self._log("Building ML pipeline...")

        self.pipeline = Pipeline(
            [
                (
                    "tfidf",
                    TfidfVectorizer(
                        ngram_range=(1, 2),
                        max_features=10000,
                        stop_words="english",
                    ),
                ),
                (
                    "svm",
                    LinearSVC(
                        random_state=42,
                        class_weight="balanced",
                        verbose=1,
                    ),
                ),
            ]
        )

    def train(
        self,
        df: pd.DataFrame,
        text_col: str = "description",
        target_col: str = "category",
    ):
        self._log("Starting data preparation...")

        initial_size = len(df)

        df = df.dropna(subset=[text_col, target_col])

        self._log(f"Removed {initial_size - len(df)} rows with missing values.")

        self._log("Cleaning text data...")
        df["clean_text"] = df[text_col].apply(self._clean_text)

        X = df["clean_text"]
        y = df[target_col]

        self._log(f"Dataset size: {len(df)}")
        self._log(f"Unique categories: {y.nunique()}")

        self._log("Splitting dataset...")
        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=0.2,
            random_state=42,
            stratify=y,
        )

        self._log(f"Train samples: {len(X_train)}")
        self._log(f"Test samples: {len(X_test)}")

        self.build_pipeline()

        self._log("Starting SVM training...")
        self.pipeline.fit(X_train, y_train)

        self._log("Training completed.")

        self._log("Running predictions on test set...")
        y_pred = self.pipeline.predict(X_test)

        accuracy = accuracy_score(y_test, y_pred)

        self._log(f"Accuracy: {accuracy:.4f}")

        report = classification_report(y_test, y_pred)

        self._log("Classification report:")
        self._log("\n" + report)

        self.save_model()

    def predict(self, description: str) -> str:
        if self.pipeline is None:
            self._log("Loading trained model...")
            self.load_model()

        clean_desc = self._clean_text(description)

        self._log(f"Predicting category for: '{description}'")

        prediction = self.pipeline.predict([clean_desc])

        self._log(f"Predicted category: {prediction[0]}")

        return prediction[0]

    def save_model(self):
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)

        joblib.dump(self.pipeline, self.model_path)

        self._log(f"Model saved to: {self.model_path}")

    def load_model(self):
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(
                f"Model file not found: {self.model_path}. "
                f"Train the model first."
            )

        self.pipeline = joblib.load(self.model_path)

        self._log("Classification model loaded successfully.")
