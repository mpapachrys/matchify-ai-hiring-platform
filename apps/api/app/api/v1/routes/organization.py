from fastapi import APIRouter

from app.api.deps import AdminUser, CurrentUser
from app.schemas.organization import (
    OrganizationOut,
    OrganizationPublicOut,
    OrganizationUpdateIn,
)
from app.services import organization_service

router = APIRouter(prefix="/organization", tags=["organization"])


@router.get("/public", response_model=OrganizationPublicOut)
async def public_organization() -> OrganizationPublicOut:
    """Branding for the sign-in screen and public job board."""
    org = await organization_service.get_organization()
    return OrganizationPublicOut(
        name=org.name,
        website=org.website,
        logo_url=org.logo_url,
        description=org.description,
        brand=org.brand,
    )


@router.get("", response_model=OrganizationOut)
async def get_organization(_: CurrentUser) -> OrganizationOut:
    org = await organization_service.get_organization()
    return OrganizationOut.build(org)


@router.patch("", response_model=OrganizationOut)
async def update_organization(data: OrganizationUpdateIn, admin: AdminUser) -> OrganizationOut:
    org = await organization_service.update_organization(admin, data)
    return OrganizationOut.build(org)
