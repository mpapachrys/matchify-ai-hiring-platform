from pydantic import BaseModel, Field

from app.models.candidate_profile import Location
from app.models.organization import BrandSettings, HiringSettings, Organization


class OrganizationOut(BaseModel):
    name: str
    website: str | None = None
    logo_url: str | None = None
    description: str | None = None
    industry: str | None = None
    size: str | None = None
    headquarters: Location = Field(default_factory=Location)
    brand: BrandSettings = Field(default_factory=BrandSettings)
    hiring: HiringSettings = Field(default_factory=HiringSettings)

    @classmethod
    def build(cls, org: Organization) -> "OrganizationOut":
        return cls(
            name=org.name,
            website=org.website,
            logo_url=org.logo_url,
            description=org.description,
            industry=org.industry,
            size=org.size,
            headquarters=org.headquarters,
            brand=org.brand,
            hiring=org.hiring,
        )


class OrganizationPublicOut(BaseModel):
    """What an unauthenticated visitor is allowed to see."""

    name: str
    website: str | None = None
    logo_url: str | None = None
    description: str | None = None
    brand: BrandSettings = Field(default_factory=BrandSettings)


class OrganizationUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    website: str | None = None
    logo_url: str | None = None
    description: str | None = None
    industry: str | None = None
    size: str | None = None
    headquarters: Location | None = None
    brand: BrandSettings | None = None
    hiring: HiringSettings | None = None
