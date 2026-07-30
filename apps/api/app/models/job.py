from datetime import UTC, datetime

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field
from pymongo import ASCENDING, DESCENDING, TEXT, IndexModel

from app.models.enums import (
    DegreeLevel,
    EmploymentType,
    JobStatus,
    LanguageProficiency,
    PipelineStage,
    SeniorityLevel,
    WorkMode,
)

#: What the three importance levels in the UI mean numerically. Recruiters pick a
#: level; the AI engine gets the weight. Nobody types 0.6 into a form.
NICE_TO_HAVE_WEIGHTS: dict[str, float] = {"nice": 0.3, "important": 0.6, "critical": 1.0}


class JobLocation(BaseModel):
    country: str | None = None
    city: str | None = None
    is_remote: bool = False


class Salary(BaseModel):
    min: int | None = None
    max: int | None = None
    currency: str = "EUR"
    period: str = "year"
    is_public: bool = True


class RequiredSkill(BaseModel):
    """A skill the candidate must have, with a minimum duration.

    `min_years` is checkable only because candidates now record skills per role
    with dates — it maps directly onto `candidate.skills[].years_experience`.
    """

    #: Stable lowercase slug. Must match the candidate export's `skills[].id`,
    #: or the two sides of the graph never join.
    slug: str
    name: str
    min_years: float | None = Field(default=None, ge=0, le=40)


class NiceToHaveSkill(BaseModel):
    slug: str
    name: str
    #: 0–1. Set from the UI's three importance levels, not typed by hand.
    weight: float = Field(default=0.6, ge=0, le=1)


class RequiredEducation(BaseModel):
    #: Ordered — a Master satisfies a Bachelor requirement. See docs/graph-export.md.
    degree_level: DegreeLevel | None = None
    field_of_study: str | None = None


class RequiredLanguage(BaseModel):
    language: str
    #: CEFR is ordered: A1 < A2 < B1 < B2 < C1 < C2 < Native.
    min_proficiency: LanguageProficiency = LanguageProficiency.B2


class MandatoryRequirements(BaseModel):
    """Binary: a candidate either meets these or does not."""

    min_years_total_experience: float | None = Field(default=None, ge=0, le=40)
    #: For roles that are explicitly junior — "no more than N years".
    max_years_total_experience: float | None = Field(default=None, ge=0, le=40)
    education: list[RequiredEducation] = Field(default_factory=list)
    skills: list[RequiredSkill] = Field(default_factory=list)
    languages: list[RequiredLanguage] = Field(default_factory=list)


class NiceToHave(BaseModel):
    """Weighted: these raise a score rather than gate it."""

    skills: list[NiceToHaveSkill] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    #: From the fixed INDUSTRIES list, matched against a candidate's
    #: `work_history[].company_industry`.
    preferred_industries: list[str] = Field(default_factory=list)


class JobStats(BaseModel):
    """Denormalized counters.

    A list of 50 job cards is one query instead of 51. Kept correct by
    incrementing inside the same transaction that writes the application.
    """

    views: int = 0
    applications: int = 0
    shortlisted: int = 0
    hired: int = 0


class Job(Document):
    created_by: PydanticObjectId

    title: str
    slug: str
    description: str = ""
    responsibilities: list[str] = Field(default_factory=list)

    # Structured rather than prose. The job page renders these as readable
    # bullets, so there is one place to edit and no risk of the prose and the
    # matching data drifting apart.
    mandatory: MandatoryRequirements = Field(default_factory=MandatoryRequirements)
    nice_to_have: NiceToHave = Field(default_factory=NiceToHave)

    #: Derived on save: every skill slug from `mandatory` and `nice_to_have`.
    #: Exists so the existing multikey and text indexes keep working — it is
    #: never edited directly.
    skills_required: list[str] = Field(default_factory=list)

    job_category: str | None = None
    seniority: SeniorityLevel = SeniorityLevel.MID
    employment_type: EmploymentType = EmploymentType.FULL_TIME
    work_mode: WorkMode = WorkMode.ONSITE
    location: JobLocation = Field(default_factory=JobLocation)
    salary: Salary | None = None
    openings: int = 1

    status: JobStatus = JobStatus.DRAFT
    pipeline_stages: list[PipelineStage] = Field(
        default_factory=lambda: [
            PipelineStage.APPLIED,
            PipelineStage.SCREENING,
            PipelineStage.INTERVIEW,
            PipelineStage.OFFER,
            PipelineStage.HIRED,
        ]
    )

    application_deadline: datetime | None = None
    published_at: datetime | None = None
    closed_at: datetime | None = None

    stats: JobStats = Field(default_factory=JobStats)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def accepts_applications(self) -> bool:
        if self.status is not JobStatus.PUBLISHED:
            return False
        if self.application_deadline and self.application_deadline < datetime.now(UTC):
            return False
        return True

    class Settings:
        name = "jobs"
        indexes = [
            # Public feed
            IndexModel(
                [("status", ASCENDING), ("published_at", DESCENDING)],
                name="status_published",
            ),
            IndexModel([("slug", ASCENDING)], unique=True, name="uniq_slug"),
            IndexModel([("created_by", ASCENDING), ("status", ASCENDING)], name="owner_status"),
            IndexModel([("skills_required", ASCENDING)], name="skills_multikey"),
            # Filter bar
            IndexModel(
                [
                    ("job_category", ASCENDING),
                    ("seniority", ASCENDING),
                    ("work_mode", ASCENDING),
                ],
                name="filters",
            ),
            IndexModel(
                [("title", TEXT), ("description", TEXT), ("skills_required", TEXT)],
                name="job_text",
                weights={"title": 10, "skills_required": 5, "description": 1},
            ),
        ]
