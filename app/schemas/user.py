from pydantic import BaseModel, EmailStr, ConfigDict, UUID4
from typing import Optional


class UserBase(BaseModel):
    email: EmailStr
    full_name: str


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    base_currency: Optional[str] = None
    locale: Optional[str] = None


class UserResponse(UserBase):
    id: UUID4
    base_currency: str = "UAH"
    locale: str = "uk"

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str
