"""JWT token management service."""

from datetime import datetime, timedelta, timezone
from typing import TypeAlias

from jose import JWTError, jwt

from app.config import backend_settings

TokenType: TypeAlias = str


class JWTService:
    """Manages JWT token creation and validation."""

    def __init__(self) -> None:
        self._secret_key = backend_settings.SECRET_KEY
        self._algorithm = backend_settings.ALGORITHM
        self._access_token_expire_minutes = (
            backend_settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        self._refresh_token_expire_days = (
            backend_settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

    def create_access_token(self, user_id: str) -> str:
        """Create an access token for the given user ID."""
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=self._access_token_expire_minutes
        )
        return jwt.encode(
            {
                "sub": user_id,
                "exp": int(expire.timestamp()),
                "token_use": "access",
            },
            self._secret_key,
            algorithm=self._algorithm,
        )

    def create_refresh_token(self, user_id: str) -> str:
        """Create a refresh token for the given user ID."""
        expire = datetime.now(timezone.utc) + timedelta(
            days=self._refresh_token_expire_days
        )
        return jwt.encode(
            {
                "sub": user_id,
                "exp": int(expire.timestamp()),
                "token_use": "refresh",
            },
            self._secret_key,
            algorithm=self._algorithm,
        )

    def decode_token(self, token: str) -> dict:
        """Decode and validate a JWT token.

        Raises JWTError if token is invalid or expired.
        """
        return jwt.decode(
            token,
            self._secret_key,
            algorithms=[self._algorithm],
        )

    def validate_refresh_token(self, token: str) -> str:
        """Validate a refresh token and extract the user ID.

        Returns the user_id from the token.
        Raises JWTError or ValueError if token is invalid.
        """
        payload = self.decode_token(token)

        if payload.get("token_use") != "refresh":
            raise JWTError("Invalid token type")

        user_id = payload.get("sub")

        if not isinstance(user_id, str):
            raise JWTError("Invalid token: missing user ID")

        return user_id
