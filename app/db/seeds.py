import uuid
from datetime import date, datetime, timezone
from sqlalchemy.orm import Session
from app.db.models import Budget, Category, Goal, RecurringInterval, RecurringTransaction, TransactionType

# Sentinel dates mark a budget as a rolling system default.
# The service layer substitutes current-month bounds when serving the response.
_SENTINEL_START = datetime(2000, 1, 1, tzinfo=timezone.utc)
_SENTINEL_END   = datetime(2099, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

# Must stay in sync with fin_pilot_ml RecommendationConfig.default_budget_limits.
# Keys are the canonical global-category names used as ML identifiers.
DEFAULT_BUDGET_LIMITS: dict[str, float] = {
    "Food & Dining":              8_000.0,
    "Transportation":             3_000.0,
    "Shopping & Retail":          5_000.0,
    "Entertainment & Recreation": 2_000.0,
    "Healthcare & Medical":       3_000.0,
    "Utilities & Services":       4_000.0,
    "Government & Legal":         1_000.0,
    "Charity & Donations":        1_000.0,
    "Financial Services":         2_000.0,
}

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


def seed_default_budgets(db: Session) -> None:
    """Insert global (user_id=NULL) budget rows for every default limit.

    Idempotent — skips categories that already have a global budget row.
    Called once during application startup after seed_categories().
    """
    existing_cat_ids: set[uuid.UUID] = {
        b.category_id
        for b in db.query(Budget).filter(Budget.user_id.is_(None)).all()
    }

    for cat_name, limit in DEFAULT_BUDGET_LIMITS.items():
        cat = (
            db.query(Category)
            .filter(Category.name == cat_name, Category.user_id.is_(None))
            .first()
        )
        if cat is None or cat.id in existing_cat_ids:
            continue
        db.add(
            Budget(
                id=uuid.uuid4(),
                user_id=None,
                category_id=cat.id,
                name=cat_name,
                limit_amount=limit,
                start_date=_SENTINEL_START,
                end_date=_SENTINEL_END,
            )
        )

    db.commit()


def seed_demo_goals(db: Session, demo_user_id: uuid.UUID) -> None:
    """Seed realistic financial goals for the demo account. Idempotent."""
    if db.query(Goal).filter(Goal.user_id == demo_user_id).first():
        return

    goals = [
        Goal(
            id=uuid.uuid4(),
            user_id=demo_user_id,
            name="Фонд надзвичайних ситуацій",
            target_amount=150_000.0,
            current_amount=68_500.0,
            deadline=date(2026, 12, 31),
        ),
        Goal(
            id=uuid.uuid4(),
            user_id=demo_user_id,
            name="Відпустка (Туреччина / Єгипет)",
            target_amount=42_000.0,
            current_amount=27_300.0,
            deadline=date(2026, 8, 1),
        ),
        Goal(
            id=uuid.uuid4(),
            user_id=demo_user_id,
            name="Новий ноутбук",
            target_amount=38_000.0,
            current_amount=31_800.0,
            deadline=date(2026, 7, 15),
        ),
        Goal(
            id=uuid.uuid4(),
            user_id=demo_user_id,
            name="Ремонт квартири",
            target_amount=250_000.0,
            current_amount=44_000.0,
            deadline=date(2027, 3, 1),
        ),
        Goal(
            id=uuid.uuid4(),
            user_id=demo_user_id,
            name="Накопичення на авто",
            target_amount=320_000.0,
            current_amount=56_000.0,
            deadline=date(2027, 12, 31),
        ),
    ]
    db.add_all(goals)
    db.commit()


def seed_demo_recurring(
    db: Session,
    demo_user_id: uuid.UUID,
    main_account_id: uuid.UUID,
    savings_account_id: uuid.UUID,
    freelance_account_id: uuid.UUID,
) -> None:
    """Seed realistic recurring transactions for the demo account. Idempotent."""
    if db.query(RecurringTransaction).filter(
        RecurringTransaction.user_id == demo_user_id
    ).first():
        return

    def _cat(name: str, tx_type: TransactionType) -> uuid.UUID | None:
        row = (
            db.query(Category)
            .filter(Category.name == name, Category.user_id.is_(None), Category.transaction_type == tx_type)
            .first()
        )
        return row.id if row else None

    utilities_id   = _cat("Utilities & Services",  TransactionType.EXPENSE)
    entertainment_id = _cat("Entertainment & Recreation", TransactionType.EXPENSE)
    salary_id      = _cat("Salary",                TransactionType.INCOME)
    income_id      = _cat("Income",                TransactionType.INCOME)
    gov_legal_id   = _cat("Government & Legal",    TransactionType.EXPENSE)
    food_id        = _cat("Food & Dining",         TransactionType.EXPENSE)

    rows = [
        # ── Monthly expenses ──────────────────────────────────────────────────
        RecurringTransaction(
            id=uuid.uuid4(), user_id=demo_user_id, account_id=main_account_id,
            category_id=utilities_id, description="Оренда квартири",
            amount=14_500.0, transaction_type=TransactionType.EXPENSE,
            interval=RecurringInterval.MONTHLY,
            start_date=date(2026, 1, 1), next_date=date(2026, 7, 1), is_active=True,
        ),
        RecurringTransaction(
            id=uuid.uuid4(), user_id=demo_user_id, account_id=main_account_id,
            category_id=entertainment_id, description="Netflix",
            amount=249.0, transaction_type=TransactionType.EXPENSE,
            interval=RecurringInterval.MONTHLY,
            start_date=date(2026, 1, 1), next_date=date(2026, 7, 1), is_active=True,
        ),
        RecurringTransaction(
            id=uuid.uuid4(), user_id=demo_user_id, account_id=main_account_id,
            category_id=entertainment_id, description="Spotify",
            amount=99.0, transaction_type=TransactionType.EXPENSE,
            interval=RecurringInterval.MONTHLY,
            start_date=date(2026, 1, 5), next_date=date(2026, 7, 5), is_active=True,
        ),
        RecurringTransaction(
            id=uuid.uuid4(), user_id=demo_user_id, account_id=main_account_id,
            category_id=utilities_id, description="Інтернет",
            amount=350.0, transaction_type=TransactionType.EXPENSE,
            interval=RecurringInterval.MONTHLY,
            start_date=date(2026, 1, 10), next_date=date(2026, 6, 10), is_active=True,
        ),
        RecurringTransaction(
            id=uuid.uuid4(), user_id=demo_user_id, account_id=main_account_id,
            category_id=utilities_id, description="Мобільний зв'язок",
            amount=150.0, transaction_type=TransactionType.EXPENSE,
            interval=RecurringInterval.MONTHLY,
            start_date=date(2026, 1, 15), next_date=date(2026, 6, 15), is_active=True,
        ),
        RecurringTransaction(
            id=uuid.uuid4(), user_id=demo_user_id, account_id=main_account_id,
            category_id=entertainment_id, description="Спортзал",
            amount=1_200.0, transaction_type=TransactionType.EXPENSE,
            interval=RecurringInterval.MONTHLY,
            start_date=date(2026, 1, 1), next_date=date(2026, 7, 1), is_active=True,
        ),
        RecurringTransaction(
            id=uuid.uuid4(), user_id=demo_user_id, account_id=main_account_id,
            category_id=gov_legal_id, description="Страхування авто",
            amount=2_400.0, transaction_type=TransactionType.EXPENSE,
            interval=RecurringInterval.MONTHLY,
            start_date=date(2026, 1, 20), next_date=date(2026, 7, 20), is_active=True,
        ),
        # ── Monthly income ────────────────────────────────────────────────────
        RecurringTransaction(
            id=uuid.uuid4(), user_id=demo_user_id, account_id=main_account_id,
            category_id=salary_id, description="Зарплата",
            amount=62_000.0, transaction_type=TransactionType.INCOME,
            interval=RecurringInterval.MONTHLY,
            start_date=date(2026, 1, 5), next_date=date(2026, 7, 5), is_active=True,
        ),
        RecurringTransaction(
            id=uuid.uuid4(), user_id=demo_user_id, account_id=freelance_account_id,
            category_id=income_id, description="Фріланс-дохід",
            amount=15_000.0, transaction_type=TransactionType.INCOME,
            interval=RecurringInterval.MONTHLY,
            start_date=date(2026, 1, 1), next_date=date(2026, 7, 1), is_active=True,
        ),
        # ── Weekly ───────────────────────────────────────────────────────────
        RecurringTransaction(
            id=uuid.uuid4(), user_id=demo_user_id, account_id=main_account_id,
            category_id=food_id, description="Продукти (тижневий бюджет)",
            amount=1_400.0, transaction_type=TransactionType.EXPENSE,
            interval=RecurringInterval.WEEKLY,
            start_date=date(2026, 1, 5), next_date=date(2026, 6, 8), is_active=True,
        ),
        # ── Yearly ───────────────────────────────────────────────────────────
        RecurringTransaction(
            id=uuid.uuid4(), user_id=demo_user_id, account_id=savings_account_id,
            category_id=None, description="Поповнення депозиту (річне)",
            amount=30_000.0, transaction_type=TransactionType.EXPENSE,
            interval=RecurringInterval.YEARLY,
            start_date=date(2026, 3, 1), next_date=date(2027, 3, 1), is_active=True,
        ),
    ]
    db.add_all(rows)
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
