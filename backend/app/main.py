from fastapi import FastAPI

from app.api.routes import auth, users

app = FastAPI(
    title="Personal Finance Management System API",
    description="Backend API for the Personal Finance Management System with ML capabilities",
    version="1.0.0",
)

app.include_router(auth.router)
app.include_router(users.router)


@app.get("/")
def read_root():
    return {"message": "API is running. Visit /docs for documentation."}
