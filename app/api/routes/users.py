from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.database import get_db
from app.schemas.user import UserResponse, UserUpdate
from app.core.auth.profile_service import UserProfileService

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
def get_me(current_user=Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserResponse)
def update_me(
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = UserProfileService(db)
    return service.update_profile(current_user.id, user_in)
