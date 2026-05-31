from sqlalchemy.orm import Session

from app.repositories.user_repository import UserRepository
from app.schemas.user import UserResponse, UserUpdate


class UserProfileService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._user_repo = UserRepository(db)

    def update_profile(self, user_id, update_data: UserUpdate) -> UserResponse:
        user = self._user_repo.get_by_id(user_id)
        if not user:
            from app.core.exceptions import NotFoundError
            raise NotFoundError("User not found")

        if update_data.full_name is not None:
            user.full_name = update_data.full_name
        if update_data.email is not None:
            user.email = update_data.email
        if update_data.base_currency is not None:
            user.base_currency = update_data.base_currency.strip().upper()

        try:
            self._db.add(user)
            self._db.commit()
            self._db.refresh(user)
            return UserResponse.model_validate(user)
        except Exception:
            self._db.rollback()
            raise
