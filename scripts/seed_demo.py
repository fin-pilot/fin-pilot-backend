#!/usr/bin/env python3
"""Demo database seeder for diploma defense presentation.

Generates a fully realistic financial history (28 months ≈ 122 weeks) for a
single demo user, including:

- Multi-currency accounts (UAH primary + USD savings)
- Monthly salary income with occasional bonus events
- 10 expense categories covering everyday spending patterns
- Seasonal spending spikes (December holidays, summer vacations)
- Anomaly expenses (large one-off medical/tech purchases)
- Budget limits per category
- UAH/USD exchange rate rows for the full history window

The resulting dataset satisfies the SARIMA cold-start guard (≥ 24 weeks) and
provides enough variance for meaningful recommendation generation.

Usage (from backend project root)::

    python scripts/seed_demo.py [--email demo@finpilot.ua] [--password demo1234]

The script is idempotent — running it twice with the same email is safe.
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Make sure the app package is importable when run from the project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from app.core.auth.password_service import PasswordService
from app.db.database import SESSION_LOCAL
from app.db.models import (
    Account,
    AccountType,
    Budget,
    Category,
    ExchangeRate,
    Transaction,
    TransactionType,
    User,
)
from app.db.seeds import seed_categories

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────

DEMO_EMAIL = "demo@finpilot.ua"
DEMO_PASSWORD = "Demo1234!"
DEMO_FULL_NAME = "Тестовий Користувач"
DEMO_BASE_CURRENCY = "UAH"

HISTORY_MONTHS = 28          # ≈ 122 weeks — comfortably above SARIMA min (24)
SALARY_UAH = 42_000.0        # monthly net salary
BONUS_PROBABILITY = 0.15     # chance of bonus in any given month
BONUS_UAH = 10_000.0

# Monthly baseline spending (UAH) per category — realistic Ukrainian budget
CATEGORY_BASELINES: dict[str, tuple[float, float]] = {
    # (mean_monthly_spend, std_dev)
    "Food & Dining":              (8_500.0, 1_200.0),
    "Transportation":             (2_800.0,   400.0),
    "Shopping & Retail":          (3_500.0,   900.0),
    "Entertainment & Recreation": (1_200.0,   500.0),
    "Healthcare & Medical":       (  600.0,   300.0),
    "Utilities & Services":       (2_200.0,   250.0),
    "Financial Services":         (  400.0,   100.0),
}

BUDGET_LIMITS: dict[str, float] = {
    "Food & Dining":              10_000.0,
    "Transportation":              3_500.0,
    "Shopping & Retail":           5_000.0,
    "Entertainment & Recreation":  2_000.0,
    "Healthcare & Medical":        1_500.0,
    "Utilities & Services":        2_500.0,
    "Financial Services":          1_000.0,
}

# One anomaly (large one-off purchase) injected per ~5 months
ANOMALY_CATEGORIES = ["Healthcare & Medical", "Shopping & Retail"]
ANOMALY_AMOUNT_RANGE = (8_000.0, 25_000.0)

# December seasonal uplift multipliers
DECEMBER_UPLIFTS: dict[str, float] = {
    "Shopping & Retail":          2.4,
    "Entertainment & Recreation": 1.8,
    "Food & Dining":              1.3,
}

# July–August vacation uplift
VACATION_UPLIFTS: dict[str, float] = {
    "Entertainment & Recreation": 2.2,
    "Transportation":             1.6,
    "Food & Dining":              1.2,
}

# USD savings account — receives 5% of each salary payment
USD_SAVINGS_PCT = 0.05
UAH_TO_USD_BASE = 41.5   # approximate mid-rate used for seeded exchange rates


# ── Helpers ────────────────────────────────────────────────────────────────────

rng = random.Random(42)   # reproducible data generation


def _rand_day_of_month(month_start: datetime, rng: random.Random) -> datetime:
    """Return a random date within the given month."""
    import calendar
    days_in_month = calendar.monthrange(month_start.year, month_start.month)[1]
    day = rng.randint(1, days_in_month)
    return month_start.replace(day=day)


def _month_start(offset_from_now: int, now: datetime) -> datetime:
    """Return the first day of the month *offset_from_now* months ago."""
    target = now - timedelta(days=offset_from_now * 30)
    return target.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


# ── Main seeding logic ─────────────────────────────────────────────────────────

def seed_demo(email: str, password: str) -> None:
    db = SESSION_LOCAL()
    try:
        _seed(db, email, password)
    finally:
        db.close()


def _seed(db, email: str, password: str) -> None:
    # ── 0. Ensure global categories exist ────────────────────────────────────
    seed_categories(db)

    # ── 1. Resolve or create demo user ───────────────────────────────────────
    existing_user: User | None = db.execute(
        select(User).where(User.email == email)
    ).scalar_one_or_none()

    if existing_user is not None:
        logger.info("Demo user already exists (%s) — checking transactions …", email)
        tx_count = db.execute(
            select(
                __import__("sqlalchemy").func.count(Transaction.id)
            ).join(Account, Transaction.account_id == Account.id).where(
                Account.user_id == existing_user.id
            )
        ).scalar()
        if tx_count and tx_count >= 100:
            logger.info("Demo data already present (%d transactions). Skipping.", tx_count)
            return
        user = existing_user
    else:
        pwd_svc = PasswordService()
        user = User(
            id=uuid.uuid4(),
            email=email,
            hashed_password=pwd_svc.hash_password(password),
            full_name=DEMO_FULL_NAME,
            base_currency=DEMO_BASE_CURRENCY,
            locale="uk",
        )
        db.add(user)
        db.flush()
        logger.info("Created demo user: %s", email)

    # ── 2. Accounts ───────────────────────────────────────────────────────────
    uah_account = Account(
        id=uuid.uuid4(),
        user_id=user.id,
        name="Monobank UAH",
        account_type=AccountType.CARD,
        balance=15_000.0,
        currency="UAH",
    )
    usd_account = Account(
        id=uuid.uuid4(),
        user_id=user.id,
        name="USD Savings",
        account_type=AccountType.CARD,
        balance=500.0,
        currency="USD",
    )
    db.add_all([uah_account, usd_account])
    db.flush()

    # ── 3. Resolve category IDs ───────────────────────────────────────────────
    all_categories: list[Category] = db.execute(
        select(Category).where(Category.user_id.is_(None))
    ).scalars().all()

    cat_by_name: dict[str, Category] = {c.name: c for c in all_categories}
    salary_cat = cat_by_name.get("Salary") or cat_by_name.get("Income")

    expense_cats: dict[str, Category] = {
        name: cat
        for name, cat in cat_by_name.items()
        if cat.transaction_type == TransactionType.EXPENSE
        and name in CATEGORY_BASELINES
    }

    # ── 4. Exchange rates for entire history window ───────────────────────────
    now = datetime.now(tz=timezone.utc)
    rate_date = _month_start(HISTORY_MONTHS + 1, now).date()
    end_date = now.date()
    seen_rate_dates: set = set()

    while rate_date <= end_date:
        if rate_date not in seen_rate_dates:
            jitter = rng.uniform(-0.5, 0.5)
            rate = UAH_TO_USD_BASE + jitter
            db.add(ExchangeRate(
                id=uuid.uuid4(),
                base_currency="UAH",
                target_currency="USD",
                rate=round(rate, 4),
                rate_date=rate_date,
                source="NBU_DEMO",
            ))
            seen_rate_dates.add(rate_date)
        rate_date += timedelta(days=1)
    db.flush()
    logger.info("Seeded %d exchange rate rows.", len(seen_rate_dates))

    # ── 5. Transactions (28 months) ───────────────────────────────────────────
    transactions: list[Transaction] = []
    anomaly_counter = 0

    for month_offset in range(HISTORY_MONTHS, 0, -1):
        m_start = _month_start(month_offset, now)
        month_num = m_start.month

        # --- Salary income (1st of month) ------------------------------------
        salary_date = m_start.replace(day=1)
        transactions.append(Transaction(
            id=uuid.uuid4(),
            account_id=uah_account.id,
            category_id=salary_cat.id if salary_cat else None,
            amount=SALARY_UAH,
            description="Зарплата — основне місце роботи",
            transaction_type=TransactionType.INCOME,
            transaction_date=salary_date.replace(tzinfo=timezone.utc),
        ))

        # Occasional bonus
        if rng.random() < BONUS_PROBABILITY:
            transactions.append(Transaction(
                id=uuid.uuid4(),
                account_id=uah_account.id,
                category_id=salary_cat.id if salary_cat else None,
                amount=BONUS_UAH,
                description="Квартальна премія",
                transaction_type=TransactionType.INCOME,
                transaction_date=_rand_day_of_month(m_start, rng).replace(tzinfo=timezone.utc),
            ))

        # USD savings transfer (5% of salary, from UAH account perspective)
        usd_transfer_uah = SALARY_UAH * USD_SAVINGS_PCT
        transactions.append(Transaction(
            id=uuid.uuid4(),
            account_id=uah_account.id,
            category_id=None,
            amount=usd_transfer_uah,
            description="Поповнення валютного рахунку",
            transaction_type=TransactionType.TRANSFER,
            transaction_date=m_start.replace(day=2, tzinfo=timezone.utc),
        ))

        # --- Expense transactions per category --------------------------------
        for cat_name, (mean, std) in CATEGORY_BASELINES.items():
            cat = expense_cats.get(cat_name)
            if cat is None:
                continue

            # Apply seasonal uplifts
            multiplier = 1.0
            if month_num == 12:
                multiplier = DECEMBER_UPLIFTS.get(cat_name, 1.0)
            elif month_num in (7, 8):
                multiplier = VACATION_UPLIFTS.get(cat_name, 1.0)

            monthly_spend = max(0.0, rng.gauss(mean * multiplier, std * multiplier))

            # Spread across 4–12 separate transactions per month
            n_txs = rng.randint(4, 12)
            for _ in range(n_txs):
                share = rng.uniform(0.5, 1.5)
                amount = round((monthly_spend / n_txs) * share, 2)
                if amount <= 0:
                    continue
                tx_date = _rand_day_of_month(m_start, rng)
                transactions.append(Transaction(
                    id=uuid.uuid4(),
                    account_id=uah_account.id,
                    category_id=cat.id,
                    amount=amount,
                    description=_sample_description(cat_name, rng),
                    transaction_type=TransactionType.EXPENSE,
                    transaction_date=tx_date.replace(tzinfo=timezone.utc),
                ))

        # --- Anomaly injection (once every ~5 months) -------------------------
        anomaly_counter += 1
        if anomaly_counter >= 5:
            anomaly_counter = 0
            anom_cat_name = rng.choice(ANOMALY_CATEGORIES)
            anom_cat = expense_cats.get(anom_cat_name)
            if anom_cat:
                anom_amount = round(rng.uniform(*ANOMALY_AMOUNT_RANGE), 2)
                transactions.append(Transaction(
                    id=uuid.uuid4(),
                    account_id=uah_account.id,
                    category_id=anom_cat.id,
                    amount=anom_amount,
                    description=_anomaly_description(anom_cat_name, rng),
                    transaction_type=TransactionType.EXPENSE,
                    transaction_date=_rand_day_of_month(m_start, rng).replace(tzinfo=timezone.utc),
                ))

    db.add_all(transactions)
    db.flush()
    logger.info("Seeded %d transactions.", len(transactions))

    # ── 6. Budget limits ──────────────────────────────────────────────────────
    import calendar as _cal
    current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_day = _cal.monthrange(now.year, now.month)[1]
    current_month_end = now.replace(day=last_day, hour=23, minute=59, second=59, microsecond=0)

    for cat_name, limit in BUDGET_LIMITS.items():
        cat = expense_cats.get(cat_name)
        if cat is None:
            continue
        db.add(Budget(
            id=uuid.uuid4(),
            user_id=user.id,
            category_id=cat.id,
            name=f"Бюджет: {cat_name}",
            limit_amount=limit,
            start_date=current_month_start,
            end_date=current_month_end,
        ))

    db.commit()
    logger.info(
        "Demo seed complete — %d transactions, %d budgets.",
        len(transactions),
        len(BUDGET_LIMITS),
    )
    logger.info("Login: email=%s  password=%s", email, password)


# ── Description samplers ──────────────────────────────────────────────────────

_DESCRIPTIONS: dict[str, list[str]] = {
    "Food & Dining": [
        "Сільпо — продукти харчування",
        "АТБ Маркет",
        "Нова Лінія — гіпермаркет",
        "Кафе «Сімейне»",
        "McDonald's Kyiv",
        "Rozetka продукти",
        "Auchan супермаркет",
        "Доставка Glovo",
        "Bolt Food замовлення",
        "Піцерія «Піца Челентано»",
    ],
    "Transportation": [
        "Uklon — таксі",
        "Bolt Driver",
        "Київ Метрополітен — поповнення",
        "Bolt автобус",
        "WOG АЗС паливо",
        "OKKO паливо",
        "UZ (Укрзалізниця) квиток",
        "FlixBus квиток",
        "Паркування центр міста",
        "Автосервіс ТО",
    ],
    "Shopping & Retail": [
        "IKEA Київ",
        "Rozetka.ua",
        "Comfy техніка",
        "Citrus електроніка",
        "H&M одяг",
        "Zara одяг",
        "Аптека Watsons",
        "Eva drugstore",
        "OLX покупка",
        "Будівельний магазин «Епіцентр»",
    ],
    "Entertainment & Recreation": [
        "Netflix підписка",
        "Spotify Premium",
        "Steam ігри",
        "Кінотеатр Multiplex",
        "Боулінг «Страйк»",
        "Концерт квиток",
        "Картинг «Speed City»",
        "Фітнес клуб World Class",
        "PlayStation Store",
        "Книгарня «Є»",
    ],
    "Healthcare & Medical": [
        "Аптека «Подорожник»",
        "Лабораторія Діла аналізи",
        "Стоматологія «Посмішка»",
        "Медзен клініка",
        "Аптека Watsons ліки",
        "МРТ центр обстеження",
        "Ортопедичний центр",
        "Оптика «Ексімер»",
    ],
    "Utilities & Services": [
        "Київенерго — електроенергія",
        "Vodafone абонплата",
        "Київстар тариф",
        "Lifecell мобільний",
        "Інтернет Київолайн",
        "Газ Нафтогаз",
        "Вода Київводоканал",
        "Управляюча компанія ЖКГ",
    ],
    "Financial Services": [
        "Monobank комісія",
        "ПриватБанк обслуговування",
        "Western Union переказ",
        "Страховка ОСЦПВ авто",
        "Bank commission FX",
    ],
}

_ANOMALY_DESCRIPTIONS: dict[str, list[str]] = {
    "Healthcare & Medical": [
        "Приватна клініка — операція",
        "МРТ з контрастом — екстрено",
        "Стоматологічний протез",
        "Офтальмологічна лазерна корекція",
    ],
    "Shopping & Retail": [
        "MacBook Air — Comfy",
        "iPhone 15 — Apple Store",
        "Телевізор Samsung 65'' — Rozetka",
        "Холодильник Bosch — IKEA",
        "Ноутбук Lenovo — Citrus",
    ],
}


def _sample_description(cat_name: str, r: random.Random) -> str:
    options = _DESCRIPTIONS.get(cat_name, [cat_name])
    return r.choice(options)


def _anomaly_description(cat_name: str, r: random.Random) -> str:
    options = _ANOMALY_DESCRIPTIONS.get(cat_name, [f"{cat_name} — велика витрата"])
    return r.choice(options)


# ── CLI entry point ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo data for diploma defense.")
    parser.add_argument("--email", default=DEMO_EMAIL, help="Demo user email")
    parser.add_argument("--password", default=DEMO_PASSWORD, help="Demo user password")
    args = parser.parse_args()
    seed_demo(args.email, args.password)


if __name__ == "__main__":
    main()
