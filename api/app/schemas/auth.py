from typing import Optional

from pydantic import BaseModel, Field


class RegisterInput(BaseModel):
    full_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)
    phone_number: Optional[str] = Field(default=None, max_length=40)


class LoginInput(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class ProfileUpdateInput(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    phone_number: Optional[str] = Field(default=None, max_length=40)


class UserOutput(BaseModel):
    user_id: str
    full_name: str
    email: Optional[str] = None
    phone_number: Optional[str] = None
    role: str


class TokenOutput(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: UserOutput
