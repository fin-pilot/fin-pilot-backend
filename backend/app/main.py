from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi_utils.tasks import repeat_every

from backend.app.db.database import SESSION_LOCAL
from backend.app.services.recurring_service import (
    process_recurring_transactions,
)
from backend.app.services.ml_service import ml_service
from ml.utils.model_loader import download_model_if_needed
from shared.logging import setup_logging

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

setup_logging()


def run_recurring_engine():
    db = SESSION_LOCAL()
    try:
        process_recurring_transactions(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    download_model_if_needed()
    ml_service.load_model()

    decorated_task = repeat_every(seconds=60 * 60 * 24)(run_recurring_engine)
    decorated_task()

    yield


app = FastAPI(
    title="Personal Finance Management System API",
    description="API for the Personal Finance Management System with ML capabilities",
    version="1.0.0",
    lifespan=lifespan,
)

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
