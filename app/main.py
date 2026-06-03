"""FastAPI application entry point.

Lifespan order:
1. Download model artifacts (no-op if already cached locally).
2. Load the global TF-IDF + LinearSVC categoriser into memory.
3. Seed default categories into PostgreSQL.
4. Start background engines: recurring-transaction processor, NBU exchange-rate refresh.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI

from app.api.exception_handlers import register_exception_handlers
from app.api.routes import (
    academic,
    accounts,
    analytics,
    auth,
    budgets,
    categories,
    goals,
    ml,
    recurring,
    transactions,
    users,
)
from app.db.database import SESSION_LOCAL
from app.db.seeds import seed_categories, seed_default_budgets, seed_demo_goals, seed_demo_recurring
from app.services.exchange_rate_service import exchange_rate_service
from app.services.ml_service import backend_ml_service
from app.services.recurring_service import process_recurring_transactions
from app.utils.model_loader import (
    download_categorizer_model_if_needed,
    download_forecaster_model_if_needed,
)

logger = logging.getLogger(__name__)


# ── Background task helpers ───────────────────────────────────────────────────

def _run_recurring_engine() -> None:
    db = SESSION_LOCAL()
    try:
        process_recurring_transactions(db)
    finally:
        db.close()


async def _recurring_task() -> None:
    """Process due recurring transactions once per day."""
    while True:
        try:
            await asyncio.to_thread(_run_recurring_engine)
        except Exception as exc:
            logger.error("Recurring transaction engine failed: %s", exc)
        await asyncio.sleep(60 * 60 * 24)


def _run_exchange_rate_refresh() -> None:
    db = SESSION_LOCAL()
    try:
        exchange_rate_service.fetch_and_store(db)
    finally:
        db.close()


async def _exchange_rate_task() -> None:
    """Fetch NBU rates once at startup, then refresh daily at 00:05 UTC."""
    try:
        await asyncio.to_thread(_run_exchange_rate_refresh)
        logger.info("Initial exchange rate fetch completed.")
    except Exception as exc:
        logger.error("Initial exchange rate fetch failed: %s", exc)

    while True:
        now = datetime.now(timezone.utc)
        next_run = (now + timedelta(days=1)).replace(
            hour=0, minute=5, second=0, microsecond=0
        )
        await asyncio.sleep((next_run - now).total_seconds())
        try:
            await asyncio.to_thread(_run_exchange_rate_refresh)
            logger.info("Exchange rates refreshed.")
        except Exception as exc:
            logger.error("Exchange rate refresh failed: %s", exc)


def _initialize_model_artifacts() -> None:
    """Download pre-trained model artifacts if not present locally."""
    download_categorizer_model_if_needed()
    download_forecaster_model_if_needed()


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(application: FastAPI):  # noqa: ARG001
    """FastAPI lifespan: startup → yield → shutdown."""
    logger.info("Application startup — initialising model artifacts …")
    await asyncio.to_thread(_initialize_model_artifacts)

    logger.info("Loading global categoriser model …")
    await asyncio.to_thread(backend_ml_service.load_global_models)

    logger.info("Seeding default categories, budgets, goals, and recurring transactions …")
    db = SESSION_LOCAL()
    try:
        import uuid as _uuid
        from app.db.models import User, Account
        seed_categories(db)
        seed_default_budgets(db)

        demo_user = db.query(User).filter(User.email == "demo@finpilot.ua").first()
        if demo_user:
            def _acct(name: str):
                row = db.query(Account).filter(
                    Account.user_id == demo_user.id, Account.name == name
                ).first()
                return row.id if row else None

            seed_demo_goals(db, demo_user.id)
            seed_demo_recurring(
                db,
                demo_user_id=demo_user.id,
                main_account_id=_acct("Main Debit Card"),
                savings_account_id=_acct("Savings / Deposit"),
                freelance_account_id=_acct("Business / Freelance Account"),
            )
    finally:
        db.close()

    logger.info("Starting background task engines …")
    bg_recurring = asyncio.create_task(_recurring_task())
    bg_exchange = asyncio.create_task(_exchange_rate_task())

    logger.info("Application startup complete.")
    yield

    logger.info("Application shutdown — cancelling background tasks …")
    bg_recurring.cancel()
    bg_exchange.cancel()
    for task in (bg_recurring, bg_exchange):
        try:
            await task
        except asyncio.CancelledError:
            pass


# ── Application instance ──────────────────────────────────────────────────────

app = FastAPI(
    title="Personal Finance Management System API",
    description=(
        "REST API for the fin-pilot personal finance management system. "
        "Powered by SARIMA time-series forecasting, TF-IDF + LinearSVC transaction "
        "classification, and a three-tier recommendation engine."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

register_exception_handlers(app)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(accounts.router)
app.include_router(categories.router)
app.include_router(transactions.router)
app.include_router(budgets.router)
app.include_router(analytics.router)
app.include_router(ml.router)
app.include_router(goals.router)
app.include_router(recurring.router)
app.include_router(academic.router)


@app.get("/", tags=["health"])
def health_check() -> dict[str, str]:
    """Basic liveness probe — returns 200 if the application is running."""
    return {"status": "ok", "message": "fin-pilot API is running. Visit /docs for documentation."}
