"""User authentication and account management service."""

from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.core.exceptions import ConflictError, NotFoundError
from backend.app.repositories.user_repository import UserRepository
from backend.app.schemas.user import UserCreate, UserResponse
from backend.app.core.auth.jwt_service import JWTService
from backend.app.core.auth.password_service import PasswordService


class AuthService:
    """Service for user authentication operations."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._user_repo = UserRepository(db)
        self._jwt_service = JWTService()
        self._password_service = PasswordService()

    def register(self, user_in: UserCreate) -> UserResponse:
        """Register a new user.

        Raises ConflictError if user with email already exists.
        """
        existing_user = self._user_repo.get_by_email(user_in.email)
        if existing_user:
            raise ConflictError("User with this email already exists")

        hashed_password = self._password_service.hash_password(user_in.password)

        with self._db.begin():
            new_user = self._user_repo.create(
                email=user_in.email,
                hashed_password=hashed_password,
                full_name=user_in.full_name,
            )

        self._db.refresh(new_user)
        return UserResponse.from_orm(new_user)

    def authenticate_user(self, email: str, password: str) -> tuple[str, str]:
        """Authenticate user and return (access_token, refresh_token).

        Raises NotFoundError if user not found.
        Raises ValueError if password is incorrect.
        """
        user = self._user_repo.get_by_email(email)
        if not user:
            raise NotFoundError("User not found")

        if not self._password_service.verify_password(
            password, user.hashed_password
        ):
            raise ValueError("Incorrect password")

        user_id = str(user.id)
        access_token = self._jwt_service.create_access_token(user_id)
        refresh_token = self._jwt_service.create_refresh_token(user_id)

        return access_token, refresh_token

    def refresh_access_token(self, refresh_token: str) -> tuple[str, str]:
        """Refresh the access token using a refresh token.

        Raises ValueError if refresh token is invalid.
        Raises NotFoundError if user not found.
        Returns new (access_token, refresh_token) pair.
        """
        try:
            user_id_str = self._jwt_service.validate_refresh_token(
                refresh_token
            )
        except Exception as exc:
            raise ValueError("Invalid refresh token") from exc

        try:
            user_id = UUID(user_id_str)
        except ValueError as exc:
            raise ValueError("Invalid user ID in token") from exc

        user = self._user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")

        new_access_token = self._jwt_service.create_access_token(user_id_str)
        new_refresh_token = self._jwt_service.create_refresh_token(user_id_str)

        return new_access_token, new_refresh_token
