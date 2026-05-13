import uuid
from sqlalchemy.orm import Session
from backend.app.db.models import Category, TransactionType

DEFAULT_EXPENSE_CATEGORIES = [
    "Food & Dining",
    "Transportation",
    "Shopping & Retail",
    "Entertainment & Recreation",
    "Healthcare & Medical",
    "Utilities & Services",
    "Financial Services",
    "Government & Legal",
    "Charity & Donations",
    "Other",
]

DEFAULT_INCOME_CATEGORIES = [
    "Income",
    "Investments",
    "Salary",
    "Other",
]


def seed_categories(db: Session) -> None:
    existing = db.query(Category).filter(Category.user_id.is_(None)).first()

    if existing:
        return

    categories = []

    for name in DEFAULT_EXPENSE_CATEGORIES:
        categories.append(
            Category(
                id=uuid.uuid4(),
                user_id=None,
                name=name,
                transaction_type=TransactionType.EXPENSE,
            )
        )

    for name in DEFAULT_INCOME_CATEGORIES:
        categories.append(
            Category(
                id=uuid.uuid4(),
                user_id=None,
                name=name,
                transaction_type=TransactionType.INCOME,
            )
        )

    db.add_all(categories)
    db.commit()
