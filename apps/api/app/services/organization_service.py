"""The single-tenant organization record.

Cached in module state because it is read on nearly every page render and
changes only when an admin edits it — the write path invalidates the cache.
"""

from datetime import UTC, datetime

from app.core.config import settings
from app.models.organization import ORG_SINGLETON_KEY, Organization
from app.models.user import User
from app.schemas.organization import OrganizationUpdateIn

_cache: Organization | None = None


async def get_organization() -> Organization:
    global _cache
    if _cache is not None:
        return _cache

    org = await Organization.find_one(Organization.key == ORG_SINGLETON_KEY)
    if org is None:
        org = Organization(
            key=ORG_SINGLETON_KEY,
            name=settings.org_name,
            website=settings.org_website,
            description=f"{settings.org_name} is hiring.",
        )
        await org.insert()

    _cache = org
    return org


async def update_organization(admin: User, data: OrganizationUpdateIn) -> Organization:
    global _cache
    org = await get_organization()

    # getattr, not model_dump(): dumping turns `headquarters`, `brand` and
    # `hiring` into plain dicts, which Beanie stores unvalidated and every
    # later attribute access then fails on.
    for key in data.model_fields_set:
        value = getattr(data, key)
        if value is not None:
            setattr(org, key, value)

    org.updated_by = admin.id
    org.updated_at = datetime.now(UTC)
    await org.save()

    _cache = org
    return org


def invalidate_cache() -> None:
    """Called by the seeder, which writes the singleton out of band."""
    global _cache
    _cache = None
