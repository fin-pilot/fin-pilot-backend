import logging
from dataclasses import dataclass
from typing import Any, cast

from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

from shared.logging import setup_logging

setup_logging()

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class EvaluationMetrics:
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    report: dict
    confusion_matrix: object | None


class CategorizerEvaluator:
    def evaluate(
        self,
        model,
        x_test,
        y_test,
        show_confusion_matrix: bool = False,
    ) -> EvaluationMetrics:
        logger.info("Evaluating model...")

        y_pred = model.predict(x_test)

        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(
            y_test,
            y_pred,
            average="weighted",
            zero_division=0,  # pyright: ignore[reportArgumentType]
        )
        recall = recall_score(
            y_test,
            y_pred,
            average="weighted",
            zero_division=0,  # pyright: ignore[reportArgumentType]
        )
        f1 = f1_score(
            y_test,
            y_pred,
            average="weighted",
            zero_division=0,  # pyright: ignore[reportArgumentType]
        )

        logger.info("Accuracy : %.4f", accuracy)
        logger.info("Precision: %.4f", precision)
        logger.info("Recall   : %.4f", recall)
        logger.info("F1 Score : %.4f", f1)

        text_report = classification_report(
            y_test,
            y_pred,
            zero_division=0,  # pyright: ignore[reportArgumentType]
        )

        logger.info("\nClassification Report:\n%s", text_report)

        report = cast(
            dict[str, Any],
            classification_report(
                y_test,
                y_pred,
                output_dict=True,
                zero_division=0,  # pyright: ignore[reportArgumentType]
            ),
        )

        cm = None
        if show_confusion_matrix:
            cm = confusion_matrix(y_test, y_pred)

            logger.info("Confusion matrix generated.")
            logger.info("\n%s", cm)

        return EvaluationMetrics(
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1_score=f1,
            report=report,
            confusion_matrix=cm,
        )
