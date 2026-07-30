from datetime import datetime

from beanie import PydanticObjectId
from pydantic import BaseModel, Field

from app.models.document import ParseStatus, UserDocument
from app.models.enums import DegreeLevel, LanguageProficiency, SeniorityLevel, WorkMode


class DraftExperience(BaseModel):
    company: str | None = None
    title: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False
    location: str | None = None
    description: str | None = None
    #: Skills used in *this* role. Required to generate — see `validate_draft`.
    #: Per-role rather than one flat list, so matching knows when a skill was
    #: last used and for how long, not just that it appears somewhere.
    skills: list[str] = Field(default_factory=list, max_length=40)
    #: Employer's industry, from the fixed INDUSTRIES list.
    company_industry: str | None = None


class DraftEducation(BaseModel):
    institution: str | None = None
    degree: str | None = None
    degree_level: DegreeLevel | None = None
    field: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    grade: str | None = None


class DraftLanguage(BaseModel):
    name: str
    level: LanguageProficiency | None = None


class DraftCertification(BaseModel):
    name: str
    issuer: str | None = None
    issued_year: int | None = Field(default=None, ge=1950, le=2100)
    credential_id: str | None = None


class DraftAchievements(BaseModel):
    career_highlights: list[str] = Field(default_factory=list, max_length=20)
    academic_distinctions: list[str] = Field(default_factory=list, max_length=20)
    awards_and_competitions: list[str] = Field(default_factory=list, max_length=20)
    projects_and_open_source: list[str] = Field(default_factory=list, max_length=20)


class DraftLinks(BaseModel):
    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None


class ResumeDraft(BaseModel):
    """What the builder wizard renders — and, since the builder is the only way
    to edit a profile, the full set of profile fields a candidate can change.

    Dates stay strings end to end — a resume prints "2019-03", not a timestamp,
    and forcing real dates here would reject perfectly good input like "2019".
    """

    full_name: str = Field(default="", max_length=120)
    headline: str | None = None
    email: str | None = None
    phone: str | None = None
    city: str | None = None
    country: str | None = None
    summary: str | None = Field(default=None, max_length=2000)

    # Not printed on the resume, but they drive job matching and are shown to
    # hiring managers — so the builder has to own them too.
    job_category: str | None = None
    seniority: SeniorityLevel | None = None
    open_to_relocate: bool = False
    work_modes: list[WorkMode] = Field(default_factory=list)

    # There is no `skills` list here and no `years_experience`. Skills belong to
    # the role that used them, and years are derived from the date ranges —
    # both are computed from `experience` rather than entered separately, so
    # they cannot drift out of step with the work history.
    experience: list[DraftExperience] = Field(default_factory=list, max_length=25)
    education: list[DraftEducation] = Field(default_factory=list, max_length=15)
    languages: list[DraftLanguage] = Field(default_factory=list, max_length=15)
    certifications: list[DraftCertification] = Field(default_factory=list, max_length=20)
    achievements: DraftAchievements = Field(default_factory=DraftAchievements)
    links: DraftLinks = Field(default_factory=DraftLinks)


class GenerateResumeIn(BaseModel):
    draft: ResumeDraft
    template: str = "professional"
    #: Make the generated PDF the resume attached to future applications.
    set_as_primary: bool = True

    # There is deliberately no `save_to_profile` flag. The builder is the only
    # editing surface for a profile, so a caller that generated without saving
    # would leave the profile permanently stale with no other way to fix it.


class GenerateResumeOut(BaseModel):
    document_id: PydanticObjectId
    filename: str
    download_url: str
    expires_in: int
    is_primary: bool


class TemplateOut(BaseModel):
    id: str
    label: str
    description: str


class ParseStatusOut(BaseModel):
    document_id: PydanticObjectId
    filename: str
    status: ParseStatus
    error: str | None = None
    model_version: str | None = None
    data: dict | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @classmethod
    def build(cls, doc: UserDocument) -> "ParseStatusOut":
        return cls(
            document_id=doc.id,
            filename=doc.file.filename,
            status=doc.parse.status,
            error=doc.parse.error,
            model_version=doc.parse.model_version,
            data=doc.parse.data,
            started_at=doc.parse.started_at,
            completed_at=doc.parse.completed_at,
        )


class ResumeDraftSeedOut(BaseModel):
    """The draft the wizard opens with, built from the candidate's profile."""

    draft: ResumeDraft
    has_profile_data: bool


class DraftIssue(BaseModel):
    """One thing blocking generation, addressed to a specific row."""

    field: str
    index: int | None = None
    message: str
