from datetime import UTC, datetime

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field
from pymongo import ASCENDING, IndexModel

from app.models.candidate_profile import Location
from app.models.enums import DocumentType, PipelineStage

#: Fixed key. Uniqueness on this field is what enforces "exactly one org".
ORG_SINGLETON_KEY = "org"


class BrandSettings(BaseModel):
    primary_color: str = "#6d28d9"
    accent_color: str = "#22d3ee"


class HiringSettings(BaseModel):
    default_pipeline_stages: list[PipelineStage] = Field(
        default_factory=lambda: [
            PipelineStage.APPLIED,
            PipelineStage.SCREENING,
            PipelineStage.INTERVIEW,
            PipelineStage.OFFER,
            PipelineStage.HIRED,
        ]
    )
    require_cover_letter: bool = False
    required_documents: list[DocumentType] = Field(
        default_factory=lambda: [
            DocumentType.RESUME,
            DocumentType.PASSPORT,
            DocumentType.DEGREE,
        ]
    )


class Organization(Document):
    """Singleton. This deployment serves exactly one hiring company.

    A document rather than env vars so managers can edit branding and the
    verification checklist from the UI without a redeploy. Read once at
    startup and cached; the cache is invalidated on write.
    """

    key: str = ORG_SINGLETON_KEY

    name: str
    website: str | None = None
    logo_url: str | None = None
    description: str | None = None
    industry: str | None = None
    size: str | None = None
    headquarters: Location = Field(default_factory=Location)

    brand: BrandSettings = Field(default_factory=BrandSettings)
    hiring: HiringSettings = Field(default_factory=HiringSettings)

    updated_by: PydanticObjectId | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "org_settings"
        indexes = [IndexModel([("key", ASCENDING)], unique=True, name="uniq_singleton")]
