import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if SQLALCHEMY_DATABASE_URL is None:
    raise ValueError("DATABASE_URL environment variable is not set")

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SESSION_LOCAL = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SESSION_LOCAL()
    try:
        yield db
    finally:
        db.close()
