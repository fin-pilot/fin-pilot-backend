import uuid
from sqlalchemy.orm import Session
from app.db.models import Category, TransactionType

# Tuples of (english_name, slug) — name is the ML internal key; slug drives i18n
DEFAULT_EXPENSE_CATEGORIES: list[tuple[str, str]] = [
    ("Food & Dining",              "food_dining"),
    ("Transportation",             "transportation"),
    ("Shopping & Retail",          "shopping_retail"),
    ("Entertainment & Recreation", "entertainment"),
    ("Healthcare & Medical",       "healthcare"),
    ("Utilities & Services",       "utilities"),
    ("Financial Services",         "financial_services"),
    ("Government & Legal",         "government_legal"),
    ("Charity & Donations",        "charity"),
    ("Other",                      "other_expense"),
]

DEFAULT_INCOME_CATEGORIES: list[tuple[str, str]] = [
    ("Income",      "income_general"),
    ("Investments", "investments"),
    ("Salary",      "salary"),
    ("Other",       "other_income"),
]


def seed_categories(db: Session) -> None:
    existing = db.query(Category).filter(Category.user_id.is_(None)).first()

    if existing:
        # Back-fill slugs for rows seeded before this field was added
        _backfill_slugs(db)
        return

    categories = []

    for name, slug in DEFAULT_EXPENSE_CATEGORIES:
        categories.append(
            Category(
                id=uuid.uuid4(),
                user_id=None,
                name=name,
                slug=slug,
                transaction_type=TransactionType.EXPENSE,
            )
        )

    for name, slug in DEFAULT_INCOME_CATEGORIES:
        categories.append(
            Category(
                id=uuid.uuid4(),
                user_id=None,
                name=name,
                slug=slug,
                transaction_type=TransactionType.INCOME,
            )
        )

    db.add_all(categories)
    db.commit()


def _backfill_slugs(db: Session) -> None:
    """Assign slugs to existing global categories that were seeded without one."""
    slug_map = {name: slug for name, slug in DEFAULT_EXPENSE_CATEGORIES + DEFAULT_INCOME_CATEGORIES}
    global_categories = (
        db.query(Category)
        .filter(Category.user_id.is_(None), Category.slug.is_(None))
        .all()
    )
    if not global_categories:
        return
    for cat in global_categories:
        cat.slug = slug_map.get(cat.name)
    db.commit()
