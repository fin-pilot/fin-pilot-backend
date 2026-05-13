from fastapi import FastAPI
from contextlib import asynccontextmanager
from ml.utils.model_loader import download_model_if_needed
from backend.app.services.ml_service import ml_service
from shared.logging import setup_logging
from app.api.routes import (
    auth,
    users,
    accounts,
    categories,
    transactions,
    budgets,
    analytics,
)

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    download_model_if_needed()
    ml_service.load_model()
    yield


app = FastAPI(
    title="Personal Finance Management System API",
    description=" API for the Personal Finance Management System with ML capabilities",
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


@app.get("/")
def read_root():
    return {"message": "API is running. Visit /docs for documentation."}
