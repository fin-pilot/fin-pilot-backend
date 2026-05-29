import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi_utils.tasks import repeat_every
from ml.utils.model_loader import (
    download_categorizer_model_if_needed,
    download_forecaster_model_if_needed,
)

from backend.app.api.exception_handlers import register_exception_handlers
from backend.app.api.routes import (
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
from backend.app.db.database import SESSION_LOCAL
from backend.app.db.seeds import seed_categories
from backend.app.services.ml_service import ml_service
from backend.app.services.recurring_service import (
    process_recurring_transactions,
)
from shared.logging import setup_logging

setup_logging()


def run_recurring_engine() -> None:
    db = SESSION_LOCAL()
    try:
        process_recurring_transactions(db)
    finally:
        db.close()


@repeat_every(seconds=60 * 60 * 24)
async def recurring_task() -> None:
    run_recurring_engine()


@asynccontextmanager
async def lifespan(application: FastAPI):  # pylint: disable=unused-argument
    download_categorizer_model_if_needed()
    download_forecaster_model_if_needed()

    ml_service.load_model()

    db = SESSION_LOCAL()

    try:
        seed_categories(db)
    finally:
        db.close()

    asyncio.create_task(recurring_task())

    yield


app = FastAPI(
    title="Personal Finance Management System API",
    description="API for the Personal Finance Management System with ML capabilities",
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
