from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import User
from app.core.config import settings
from ml.models.categorizer import TransactionCategorizer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
ml_categorizer = TransactionCategorizer()


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        user_id = payload.get("sub")
        if not user_id:
            raise credentials_exception

        if payload.get("token_use") not in (None, "access"):
            raise credentials_exception

    except JWTError as exc:
        raise credentials_exception from exc

    try:
        uid_key = UUID(str(user_id))
    except ValueError as exc:
        raise credentials_exception from exc

    user = db.query(User).filter(User.id == uid_key).first()

    if not user:
        raise credentials_exception

    return user


def get_categorizer():
    if ml_categorizer.pipeline is None:
        try:
            ml_categorizer.load_model()
        except FileNotFoundError:
            pass
    return ml_categorizer
