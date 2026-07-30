from beanie import PydanticObjectId
from pydantic import BaseModel, Field

from app.models.candidate_profile import (
    CandidateProfile,
    Education,
    Experience,
    Language,
    Links,
    Location,
    SalaryExpectation,
)
from app.models.enums import SeniorityLevel, WorkMode


class CandidateProfileIn(BaseModel):
    headline: str | None = None
    summary: str | None = None
    job_category: str | None = None
    seniority: SeniorityLevel | None = None
    location: Location = Field(default_factory=Location)
    open_to_relocate: bool = False
    work_modes: list[WorkMode] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    years_experience: float | None = Field(default=None, ge=0, le=60)
    expected_salary: SalaryExpectation | None = None
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    links: Links = Field(default_factory=Links)


class CandidateProfileOut(CandidateProfileIn):
    id: PydanticObjectId
    user_id: PydanticObjectId
    full_name: str
    email: str
    avatar_url: str | None = None
    primary_resume_id: PydanticObjectId | None = None
    saved_job_ids: list[PydanticObjectId] = Field(default_factory=list)
    completion_percent: int = 0

    @classmethod
    def build(cls, profile: CandidateProfile, *, full_name: str, email: str,
              avatar_url: str | None = None) -> "CandidateProfileOut":
        return cls(
            id=profile.id,
            user_id=profile.user_id,
            full_name=full_name,
            email=email,
            avatar_url=avatar_url,
            headline=profile.headline,
            summary=profile.summary,
            job_category=profile.job_category,
            seniority=profile.seniority,
            location=profile.location,
            open_to_relocate=profile.open_to_relocate,
            work_modes=profile.work_modes,
            skills=profile.skills,
            years_experience=profile.years_experience,
            expected_salary=profile.expected_salary,
            experience=profile.experience,
            education=profile.education,
            languages=profile.languages,
            links=profile.links,
            primary_resume_id=profile.primary_resume_id,
            saved_job_ids=profile.saved_job_ids,
            completion_percent=profile.completion_percent,
        )
