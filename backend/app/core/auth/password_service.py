"""Password hashing and verification service."""

from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher


class PasswordService:
    """Manages password hashing and verification using bcrypt."""

    def __init__(self) -> None:
        self._pwd_context = PasswordHash((BcryptHasher(),))

    def hash_password(self, password: str) -> str:
        """Hash a plaintext password using bcrypt."""
        return self._pwd_context.hash(password)

    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify a plaintext password against a bcrypt hash."""
        return self._pwd_context.verify(password, hashed_password)
