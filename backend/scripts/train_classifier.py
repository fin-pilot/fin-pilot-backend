import os
import sys
import pandas as pd
import logging

# Налаштування шляхів, щоб скрипт бачив модулі з app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ml.nlp_categorizer import TransactionCategorizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_training():
    # Вказуємо правильну назву вашого файлу .parquet
    dataset_path = os.path.join(
        os.path.dirname(__file__), "..", "data", "0000.parquet"
    )

    if not os.path.exists(dataset_path):
        logger.error(f"Датасет не знайдено за шляхом: {dataset_path}")
        return

    logger.info("Завантаження датасету Parquet...")
    # ВИКОРИСТОВУЄМО read_parquet ЗАМІСТЬ read_csv
    df = pd.read_parquet(dataset_path)

    # Виводимо перші кілька рядків, щоб переконатися, що дані завантажились правильно
    logger.info(f"Завантажено {len(df)} рядків. Колонки: {df.columns.tolist()}")

    # ПЕРЕВІРКА КОЛОНОК:
    text_column = "transaction_description"
    category_column = "category"

    if text_column not in df.columns or category_column not in df.columns:
        logger.error(
            f"У датасеті відсутні потрібні колонки. Наявні: {df.columns.tolist()}"
        )
        return

    categorizer = TransactionCategorizer()
    categorizer.train(df, text_col=text_column, target_col=category_column)
    logger.info("Тренування успішно завершено! Модель збережена.")


if __name__ == "__main__":
    run_training()
