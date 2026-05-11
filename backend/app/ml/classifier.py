import pandas as pd
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split


class TransactionCategorizer:
    def __init__(self, model_path="backend/app/ml/models/svm_categorizer.pkl"):
        self.model_path = model_path
        self.pipeline = None

    def build_pipeline(self):
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
                ("svm", LinearSVC(random_state=42, class_weight="balanced")),
            ]
        )

    def train(
        self,
        df: pd.DataFrame,
        text_col: str = "description",
        target_col: str = "category",
    ):
        if self.pipeline is None:
            self.build_pipeline()

        X = df[text_col].astype(str)
        y = df[target_col]
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        self.pipeline.fit(X_train, y_train)

        y_pred = self.pipeline.predict(X_test)

        self.save_model()

    def predict(self, description: str) -> str:
        if self.pipeline is None:
            self.load_model()
        return self.pipeline.predict([description])[0]

    def save_model(self):
        joblib.dump(self.pipeline, self.model_path)

    def load_model(self):
        try:
            self.pipeline = joblib.load(self.model_path)
        except Exception as e:
            raise
