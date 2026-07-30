from datetime import UTC, datetime

from beanie import Document, PydanticObjectId
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class RefreshToken(Document):
    """One row per issued refresh token.

    Only the SHA-256 digest is stored, so a database dump yields no usable
    sessions. Tokens rotate on every refresh and share a `family_id`: if an
    already-revoked token from a family is presented, that is a replay signal
    and the entire family is revoked.
    """

    user_id: PydanticObjectId
    token_hash: str
    family_id: str

    user_agent: str | None = None
    ip: str | None = None

    expires_at: datetime
    revoked_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_usable(self) -> bool:
        if self.revoked_at is not None:
            return False
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        return expires > datetime.now(UTC)

    class Settings:
        name = "refresh_tokens"
        indexes = [
            IndexModel([("token_hash", ASCENDING)], unique=True, name="uniq_token_hash"),
            IndexModel([("user_id", ASCENDING)], name="by_user"),
            IndexModel([("family_id", ASCENDING)], name="by_family"),
            # TTL: Mongo garbage-collects expired sessions with no cron of ours.
            IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0, name="ttl_expiry"),
        ]
