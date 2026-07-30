from datetime import datetime

from beanie import PydanticObjectId
from pydantic import BaseModel, EmailStr, Field

from app.models.enums import Role
from app.models.user import User


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)
    role: Role
    phone: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: PydanticObjectId
    email: EmailStr
    full_name: str
    role: Role
    phone: str | None = None
    avatar_url: str | None = None
    is_admin: bool
    is_email_verified: bool
    created_at: datetime

    @classmethod
    def from_user(cls, user: User) -> "UserOut":
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            phone=user.phone,
            avatar_url=user.avatar_url,
            is_admin=user.is_admin,
            is_email_verified=user.is_email_verified,
            created_at=user.created_at,
        )


class SessionOut(BaseModel):
    """Returned by register/login/refresh/me.

    No token in the body on purpose — tokens live in httpOnly cookies so that
    JavaScript (and therefore XSS) cannot read them.
    """

    user: UserOut


class UserUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = None
    avatar_url: str | None = None


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)
