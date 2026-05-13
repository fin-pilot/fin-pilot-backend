import uuid
from sqlalchemy.orm import Session
from backend.app.db.models import Category, TransactionType

DEFAULT_EXPENSE_CATEGORIES = [
    "Auto & Transport",
    "Bills & Utilities",
    "Entertainment",
    "Fees & Charges",
    "Food & Dining",
    "Groceries",
    "Health & Fitness",
    "Home",
    "Kids",
    "Misc Expenses",
    "Personal Care",
    "Pets",
    "Shopping",
    "Taxes",
    "Travel",
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
                type=TransactionType.EXPENSE,
            )
        )

    for name in DEFAULT_INCOME_CATEGORIES:
        categories.append(
            Category(
                id=uuid.uuid4(),
                user_id=None,
                name=name,
                type=TransactionType.INCOME,
            )
        )

    db.add_all(categories)
    db.commit()
