from datetime import datetime

from beanie import PydanticObjectId
from pydantic import BaseModel, Field

from app.models.enums import (
    EmploymentType,
    JobStatus,
    PipelineStage,
    SeniorityLevel,
    WorkMode,
)
from app.models.job import (
    Job,
    JobLocation,
    JobStats,
    MandatoryRequirements,
    NiceToHave,
    Salary,
)


class JobCreateIn(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    description: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    # Structured, not prose. `skills_required` is derived from these on save.
    mandatory: MandatoryRequirements = Field(default_factory=MandatoryRequirements)
    nice_to_have: NiceToHave = Field(default_factory=NiceToHave)
    job_category: str | None = None
    seniority: SeniorityLevel = SeniorityLevel.MID
    employment_type: EmploymentType = EmploymentType.FULL_TIME
    work_mode: WorkMode = WorkMode.ONSITE
    location: JobLocation = Field(default_factory=JobLocation)
    salary: Salary | None = None
    openings: int = Field(default=1, ge=1, le=999)
    application_deadline: datetime | None = None
    pipeline_stages: list[PipelineStage] | None = None
    status: JobStatus = JobStatus.DRAFT


class JobUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=160)
    description: str | None = None
    responsibilities: list[str] | None = None
    mandatory: MandatoryRequirements | None = None
    nice_to_have: NiceToHave | None = None
    job_category: str | None = None
    seniority: SeniorityLevel | None = None
    employment_type: EmploymentType | None = None
    work_mode: WorkMode | None = None
    location: JobLocation | None = None
    salary: Salary | None = None
    openings: int | None = Field(default=None, ge=1, le=999)
    application_deadline: datetime | None = None
    status: JobStatus | None = None


class JobOut(BaseModel):
    """Public shape. No draft-only fields, no internal counters beyond
    application volume (which is shown to candidates as social proof)."""

    id: PydanticObjectId
    title: str
    slug: str
    description: str
    responsibilities: list[str]
    mandatory: MandatoryRequirements
    nice_to_have: NiceToHave
    #: Flat slug list, derived. Kept on the response so job cards can render
    #: skill chips without walking the structured requirements.
    skills_required: list[str]
    job_category: str | None
    seniority: SeniorityLevel
    employment_type: EmploymentType
    work_mode: WorkMode
    location: JobLocation
    salary: Salary | None
    openings: int
    status: JobStatus
    application_deadline: datetime | None
    published_at: datetime | None
    created_at: datetime
    applications_count: int = 0

    # Populated for authenticated candidates so the UI can render
    # "Applied" instead of the apply button.
    has_applied: bool = False
    is_saved: bool = False

    @classmethod
    def build(cls, job: Job, *, has_applied: bool = False, is_saved: bool = False) -> "JobOut":
        salary = job.salary if (job.salary and job.salary.is_public) else None
        return cls(
            id=job.id,
            title=job.title,
            slug=job.slug,
            description=job.description,
            responsibilities=job.responsibilities,
            mandatory=job.mandatory,
            nice_to_have=job.nice_to_have,
            skills_required=job.skills_required,
            job_category=job.job_category,
            seniority=job.seniority,
            employment_type=job.employment_type,
            work_mode=job.work_mode,
            location=job.location,
            salary=salary,
            openings=job.openings,
            status=job.status,
            application_deadline=job.application_deadline,
            published_at=job.published_at,
            created_at=job.created_at,
            applications_count=job.stats.applications,
            has_applied=has_applied,
            is_saved=is_saved,
        )


class JobManagerOut(JobOut):
    """Adds the fields only a hiring manager may see."""

    created_by: PydanticObjectId
    can_edit: bool = False
    pipeline_stages: list[PipelineStage] = Field(default_factory=list)
    stats: JobStats = Field(default_factory=JobStats)
    updated_at: datetime | None = None

    @classmethod
    def build_manager(cls, job: Job, *, can_edit: bool) -> "JobManagerOut":
        data = JobOut.build(job).model_dump()
        # Managers see the salary band even when it is hidden from candidates.
        data["salary"] = job.salary
        return cls(
            **data,
            created_by=job.created_by,
            can_edit=can_edit,
            pipeline_stages=job.pipeline_stages,
            stats=job.stats,
            updated_at=job.updated_at,
        )
