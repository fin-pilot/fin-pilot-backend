from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import User
from app.schemas.user import UserCreate, Token, UserResponse
from app.core.config import settings
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher
from jose import jwt

router = APIRouter(prefix="/api/auth", tags=["auth"])
pwd_context = PasswordHash((BcryptHasher(),))


@router.post("/register", response_model=UserResponse)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_in.email).first()
    if user:
        raise HTTPException(status_code=400, detail="User already exists")

    hashed_password = pwd_context.hash(user_in.password)
    new_user = User(
        email=user_in.email,
        hashed_password=hashed_password,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == form_data.username).first()

    if not user or not pwd_context.verify(
        form_data.password, user.hashed_password
    ):
        raise HTTPException(
            status_code=401, detail="Incorrect email or password"
        )

    access_token = jwt.encode(
        {"sub": str(user.id)}, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )

    return {"access_token": access_token, "token_type": "bearer"}
