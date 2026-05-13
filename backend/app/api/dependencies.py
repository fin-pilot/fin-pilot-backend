from uuid import UUID

from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from jose import jwt
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.db.models import User
from backend.app.services.ml_service import (
    ml_service,
)
from shared.config import backend_settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            backend_settings.SECRET_KEY,
            algorithms=[backend_settings.ALGORITHM],
        )

        user_id = payload.get("sub")

        if not user_id:
            raise credentials_exception

        if payload.get("token_use") not in (
            None,
            "access",
        ):
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
    return ml_service.categorizer
