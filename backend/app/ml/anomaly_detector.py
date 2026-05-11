import pandas as pd
from sklearn.ensemble import IsolationForest
import joblib


class AnomalyDetector:
    def __init__(self, model_path="backend/app/ml/models/anomaly_detector.pkl"):
        self.model_path = model_path
        self.model = IsolationForest(contamination=0.01, random_state=42)
        self.is_trained = False

    def train(self, df: pd.DataFrame, feature_cols=["amount"]):
        X = df[feature_cols]
        self.model.fit(X)
        self.is_trained = True
        joblib.dump(self.model, self.model_path)

    def detect(self, amount: float) -> bool:
        if not self.is_trained:
            try:
                self.model = joblib.load(self.model_path)
                self.is_trained = True
            except Exception as e:
                raise ValueError("Model not found. Call train() first.")

        prediction = self.model.predict([[amount]])
        is_anomaly = bool(prediction[0] == -1)
        return is_anomaly
