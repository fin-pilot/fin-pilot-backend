import logging

from sklearn.model_selection import train_test_split

from ml.categorizing.data_loader import CategorizerDataLoader
from ml.categorizing.evaluator import CategorizerEvaluator
from ml.categorizing.model import TransactionCategorizer
from shared.config import ml_settings
from shared.logging import setup_logging

setup_logging()

logger = logging.getLogger(__name__)


class CategorizerTrainer:
    def __init__(self) -> None:
        self.config = ml_settings
        self.data_loader = CategorizerDataLoader()
        self.evaluator = CategorizerEvaluator()
        self.model = TransactionCategorizer(self.config)

    def run(self) -> None:
        logger.info("Starting training pipeline.")

        x, y = self.data_loader.load()

        x_train, x_test, y_train, y_test = self._split_data(x, y)

        logger.info("Training model...")

        self.model.train(x_train, y_train)

        metrics = self.evaluator.evaluate(
            model=self.model.pipeline, x_test=x_test, y_test=y_test
        )

        logger.info("Final accuracy: %.4f", metrics.accuracy)

        logger.info("Saving model...")

        self.model.save_model()

        logger.info("Training completed.")

    def _split_data(self, x, y):
        return train_test_split(
            x,
            y,
            test_size=self.config.data.test_size,
            random_state=self.config.data.random_state,
            stratify=y,
        )


def main() -> None:
    trainer = CategorizerTrainer()
    trainer.run()


if __name__ == "__main__":
    main()
