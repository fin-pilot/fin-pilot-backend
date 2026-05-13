import logging
from sklearn.model_selection import train_test_split
from shared.config import ml_settings
from shared.logging import setup_logging
from ml.models.categorizer import TransactionCategorizer
from ml.utils.data_loader import load_categorizer_data
from ml.evaluation.categorizer_evaluator import evaluate_categorizer_model

setup_logging()
logger = logging.getLogger(__name__)


def main():
    logger.info("Starting training pipeline.")

    x, y = load_categorizer_data()

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=(ml_settings.data.test_size),
        random_state=(ml_settings.data.random_state),
        stratify=y,
    )

    logger.info("Initializing model...")

    model = TransactionCategorizer(ml_settings)

    logger.info("Training model...")

    model.train(x_train, y_train)

    metrics = evaluate_categorizer_model(model.pipeline, x_test, y_test)

    logger.info(
        "Final accuracy: %.4f",
        metrics["accuracy"],
    )

    logger.info("Saving model...")

    model.save_model()

    logger.info("Training completed.")


if __name__ == "__main__":
    main()
