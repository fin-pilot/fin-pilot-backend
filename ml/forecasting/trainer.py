import logging

from ml.forecasting.data_loader import ForecastingDataLoader
from ml.forecasting.evaluator import ForecastEvaluator
from ml.forecasting.model import TransactionForecaster
from ml.forecasting.preprocessing import ForecastPreprocessor
from shared.config import ml_settings
from shared.logging import setup_logging

setup_logging()

logger = logging.getLogger(__name__)


class ForecastTrainer:
    def __init__(self) -> None:
        self.data_loader = ForecastingDataLoader()

        self.preprocessor = ForecastPreprocessor()

        self.evaluator = ForecastEvaluator()

        self.model = TransactionForecaster(ml_settings)

    def run(self) -> None:
        logger.info("Starting forecasting pipeline.")

        df = self.data_loader.load()

        if df.empty:
            raise ValueError("Forecasting dataset is empty.")

        series_df = self.preprocessor.prepare_series(df=df, target="expense")

        if series_df.empty:
            raise ValueError("Prepared forecasting series is empty.")

        series = series_df.set_index("ds")["y"]

        logger.info("Prepared time series with %s observations.", len(series))

        logger.info(
            "Date range: %s -> %s", series.index.min(), series.index.max()
        )

        logger.info(
            "Mean=%.2f Std=%.2f", float(series.mean()), float(series.std())
        )

        self.model.check_stationarity(series)

        metrics = self.evaluator.evaluate_walk_forward(
            model=self.model,
            series=series,
            initial_train_size=max(14, int(len(series) * 0.6)),
            step=max(1, int(len(series) * 0.1)),
        )

        logger.info("Final MAE : %.4f", metrics.mae)
        logger.info("Final RMSE: %.4f", metrics.rmse)
        logger.info("Final WAPE: %.4f", metrics.wape)

        if metrics.wape > 1.0:
            logger.warning(
                "Model quality is poor (WAPE > 1.0). "
                "Training will continue, but forecasts may be unreliable."
            )

        logger.info("Training forecasting model on full dataset...")

        self.model.fit(series)

        logger.info("Saving forecasting model...")

        self.model.save_model()

        logger.info("Forecasting training completed successfully.")


def main() -> None:
    trainer = ForecastTrainer()

    trainer.run()


if __name__ == "__main__":
    main()
