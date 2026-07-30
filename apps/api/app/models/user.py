from datetime import UTC, datetime

from beanie import Document
from pydantic import EmailStr, Field, field_validator
from pymongo import ASCENDING, DESCENDING, IndexModel

from app.models.enums import Role


class User(Document):
    """Identity only. Heavy candidate data lives in CandidateProfile so that
    this collection — read on every authenticated request — stays small."""

    email: EmailStr
    password_hash: str
    role: Role

    full_name: str
    phone: str | None = None
    avatar_url: str | None = None

    # Single-tenant: there is one company, so managers need no company_id.
    # `is_admin` gates organization settings and cross-manager job edits.
    is_admin: bool = False

    is_active: bool = True
    is_email_verified: bool = False

    last_login_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, v: str) -> str:
        return v.strip().lower() if isinstance(v, str) else v

    @property
    def is_manager(self) -> bool:
        return self.role is Role.HIRING_MANAGER

    class Settings:
        name = "users"
        indexes = [
            IndexModel([("email", ASCENDING)], unique=True, name="uniq_email"),
            IndexModel([("role", ASCENDING), ("created_at", DESCENDING)], name="role_created"),
        ]
