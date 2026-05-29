from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher


class PasswordService:
    def __init__(self) -> None:
        self._pwd_context = PasswordHash((BcryptHasher(),))

    def hash_password(self, password: str) -> str:
        return self._pwd_context.hash(password)

    def verify_password(self, password: str, hashed_password: str) -> bool:
        return self._pwd_context.verify(password, hashed_password)
