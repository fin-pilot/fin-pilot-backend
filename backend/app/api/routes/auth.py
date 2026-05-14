from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.schemas.user import (
    RefreshTokenRequest,
    Token,
    UserCreate,
    UserResponse,
)
from backend.app.core.auth.service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    service = AuthService(db)
    return service.register(user_in)


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    from backend.app.core.exceptions import ValidationError

    service = AuthService(db)
    try:
        access_token, refresh_tok = service.authenticate_user(
            form_data.username, form_data.password
        )
    except ValueError as exc:
        raise ValidationError("Incorrect email or password") from exc

    return {
        "access_token": access_token,
        "refresh_token": refresh_tok,
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=Token)
def refresh_access_token(
    body: RefreshTokenRequest, db: Session = Depends(get_db)
):
    from backend.app.core.exceptions import ValidationError

    service = AuthService(db)
    try:
        access_token, refresh_tok = service.refresh_access_token(
            body.refresh_token
        )
    except (ValueError, Exception) as exc:
        raise ValidationError("Invalid refresh token") from exc

    return {
        "access_token": access_token,
        "refresh_token": refresh_tok,
        "token_type": "bearer",
    }
