from fastapi import FastAPI

from app.api.routes import (
    auth,
    users,
    accounts,
    categories,
    transactions,
    budgets,
    analytics,
)

app = FastAPI(
    title="Personal Finance Management System API",
    description=" API for the Personal Finance Management System with ML capabilities",
    version="1.0.0",
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
