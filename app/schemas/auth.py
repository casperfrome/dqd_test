from pydantic import Field

from app.schemas.common import BaseSchema


class RegisterRequest(BaseSchema):
    username: str = Field(min_length=3, max_length=32)
    nickname: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    bio: str = Field(default="", max_length=280)


class LoginRequest(BaseSchema):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=128)


class TokenResponse(BaseSchema):
    access_token: str
    token_type: str = "bearer"
