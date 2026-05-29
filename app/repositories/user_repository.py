"""User persistence operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User


class UserRepository:
    """Repository for user data access operations."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_email(self, email: str) -> User | None:
        """Get a user by email address."""
        stmt = select(User).where(User.email == email)

        return self._db.scalar(stmt)

    def get_by_id(self, user_id: UUID) -> User | None:
        """Get a user by ID."""
        stmt = select(User).where(User.id == user_id)

        return self._db.scalar(stmt)

    def create(
        self,
        email: str,
        hashed_password: str,
        full_name: str | None = None,
    ) -> User:
        """Create and persist a new user."""
        user = User(
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
        )

        self._db.add(user)

        return user
