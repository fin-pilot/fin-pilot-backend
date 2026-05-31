import asyncio
from contextlib import asynccontextmanager

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

    # 4. Start the recurring-transaction background engine
    bg_task = asyncio.create_task(recurring_task())

    yield

    bg_task.cancel()
    try:
        await bg_task
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
