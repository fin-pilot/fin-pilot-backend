import logging
from shared.config import ml_settings
from shared.logging import setup_logging
from ml.models.forecaster import ExpenseForecaster
from ml.utils.data_loader import load_forecaster_data
from ml.evaluation.forecaster_evaluator import evaluate_forecaster_model

setup_logging()
logger = logging.getLogger(__name__)


def main():
    logger.info("Starting forecasting training pipeline.")

    df = load_forecaster_data()

    if df.empty:
        logger.warning("Forecasting dataset is empty.")

        return

    logger.info("Splitting dataset...")

    test_size = int(len(df) * ml_settings.data.test_size)

    train_df = df.iloc[:-test_size]
    test_df = df.iloc[-test_size:]

    logger.info("Initializing forecasting model...")

    model = ExpenseForecaster(ml_settings)

    logger.info("Training forecasting model...")

    is_trained = model.train(train_df)

    if not is_trained:
        logger.warning("Forecasting model training failed.")

        return

    logger.info("Preparing evaluation data...")

    actual = model.preprocess(test_df)

    metrics = evaluate_forecaster_model(
        model=model,
        actual=actual,
        forecast_steps=len(actual),
    )

    logger.info(
        "Final RMSE: %.4f",
        metrics["rmse"],
    )

    logger.info("Saving forecasting model...")

    model.save_model()

    logger.info("Forecasting training completed.")


if __name__ == "__main__":
    main()
