import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI

from app.utils.model_loader import (
    download_categorizer_model_if_needed,
    download_forecaster_model_if_needed,
)

from app.api.exception_handlers import register_exception_handlers
from app.api.routes import (
    auth,
    users,
    accounts,
    categories,
    transactions,
    budgets,
    analytics,
    ml,
    goals,
    recurring,
)
from app.db.database import SESSION_LOCAL
from app.db.seeds import seed_categories
from app.services.exchange_rate_service import exchange_rate_service
from app.services.ml_service import backend_ml_service
from app.services.recurring_service import process_recurring_transactions


def run_recurring_engine() -> None:
    db = SESSION_LOCAL()
    try:
        process_recurring_transactions(db)
    finally:
        db.close()


async def recurring_task() -> None:
    while True:
        try:
            await asyncio.to_thread(run_recurring_engine)
        except Exception as exc:
            print(f"Error in recurring task: {exc}")
        await asyncio.sleep(60 * 60 * 24)


def run_exchange_rate_refresh() -> None:
    db = SESSION_LOCAL()
    try:
        exchange_rate_service.fetch_and_store(db)
    finally:
        db.close()


async def exchange_rate_task() -> None:
    """Fetch NBU rates once at startup, then refresh daily at 00:05 UTC."""
    try:
        await asyncio.to_thread(run_exchange_rate_refresh)
    except Exception as exc:
        print(f"Error in initial exchange rate fetch: {exc}")

    while True:
        now = datetime.now(timezone.utc)
        next_run = (now + timedelta(days=1)).replace(
            hour=0, minute=5, second=0, microsecond=0
        )
        await asyncio.sleep((next_run - now).total_seconds())
        try:
            await asyncio.to_thread(run_exchange_rate_refresh)
        except Exception as exc:
            print(f"Error in exchange rate task: {exc}")


def initialize_model_artifacts() -> None:
    """Download pre-trained model artifacts if not present locally."""
    download_categorizer_model_if_needed()
    download_forecaster_model_if_needed()


@asynccontextmanager
async def lifespan(application: FastAPI):
    # 1. Download artifacts (no-op if already present)
    await asyncio.to_thread(initialize_model_artifacts)

    # 2. Load the shared categoriser model into memory
    await asyncio.to_thread(backend_ml_service.load_global_models)

    # 3. Seed global categories
    db = SESSION_LOCAL()
    try:
        seed_categories(db)
    finally:
        db.close()

    # 4. Start background engines
    bg_recurring = asyncio.create_task(recurring_task())
    bg_exchange = asyncio.create_task(exchange_rate_task())

    yield

    bg_recurring.cancel()
    bg_exchange.cancel()
    for task in (bg_recurring, bg_exchange):
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Personal Finance Management System API",
    description=(
        "API for the Personal Finance Management System "
        "with SARIMA forecasting and ML-powered recommendations."
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


@app.get("/")
def read_root():
    return {"message": "API is running. Visit /docs for documentation."}
