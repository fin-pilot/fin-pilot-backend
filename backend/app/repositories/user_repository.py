"""User persistence operations."""

from sqlalchemy.orm import Session

from backend.app.db.models import User


class UserRepository:
    """Repository for user data access operations."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_email(self, email: str) -> User | None:
        """Get a user by email address."""
        return self._db.query(User).filter(User.email == email).first()

    def get_by_id(self, user_id) -> User | None:
        """Get a user by ID."""
        return self._db.query(User).filter(User.id == user_id).first()

    def create(
        self, email: str, hashed_password: str, full_name: str | None = None
    ) -> User:
        """Create and persist a new user."""
        user = User(
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
        )
        self._db.add(user)
        return user
