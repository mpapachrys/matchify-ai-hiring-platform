from datetime import UTC, date, datetime

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field, field_validator
from pymongo import ASCENDING, TEXT, IndexModel

from app.models.enums import DegreeLevel, LanguageProficiency, SeniorityLevel, WorkMode


class Location(BaseModel):
    country: str | None = None
    city: str | None = None
    postal_code: str | None = None
    address: str | None = None


class SalaryExpectation(BaseModel):
    min: int | None = None
    max: int | None = None
    currency: str = "EUR"
    period: str = "year"  # year | month | day | hour


class Experience(BaseModel):
    company: str
    title: str
    start_date: date
    end_date: date | None = None
    is_current: bool = False
    location: str | None = None
    description: str | None = None
    #: Skills used in this specific role. `CandidateProfile.skills` is the union
    #: of these — kept per-role so matching can tell recent from long-ago use.
    skills: list[str] = Field(default_factory=list)
    #: The employer's industry, from the fixed INDUSTRIES list. One graph node
    #: per industry rather than one per spelling.
    company_industry: str | None = None


class Education(BaseModel):
    institution: str
    #: Free text as printed on the resume, e.g. "BSc Computer Engineering".
    degree: str
    #: Normalized level for the graph. `degree` alone would create a separate
    #: node for every spelling of the same qualification.
    degree_level: DegreeLevel | None = None
    field: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    grade: str | None = None


#: Free-text proficiency wordings, mapped onto CEFR. Covers both what documents
#: written before the enum existed contain, and what an LLM returns when a CV
#: says "fluent" rather than "C1".
_PROFICIENCY_ALIASES: dict[str, str] = {
    "native": "Native",
    "mother tongue": "Native",
    "bilingual": "Native",
    "fluent": "C1",
    "advanced": "C1",
    "professional": "B2",
    "professional working": "B2",
    "professional working proficiency": "B2",
    "intermediate": "B1",
    "conversational": "B1",
    "elementary": "A2",
    "basic": "A2",
    "beginner": "A1",
}


class Language(BaseModel):
    name: str
    #: CEFR, or Native. A closed vocabulary because the AI team keys graph nodes
    #: on it; free text would fragment "fluent" / "Fluent" / "C2".
    level: LanguageProficiency = LanguageProficiency.B2

    @field_validator("level", mode="before")
    @classmethod
    def _coerce_level(cls, value: object) -> object:
        """Accept legacy and free-text wordings instead of failing to load.

        Documents written before this field was an enum hold "native" /
        "professional". Without this, reading such a profile raises a validation
        error and the whole record becomes unreadable — a far worse outcome than
        an approximate mapping.
        """
        if not isinstance(value, str):
            return value
        cleaned = value.strip()
        if cleaned.upper() in {level.value.upper() for level in LanguageProficiency}:
            return cleaned.upper() if len(cleaned) == 2 else cleaned.title()
        return _PROFICIENCY_ALIASES.get(cleaned.lower(), LanguageProficiency.B2.value)


class Certification(BaseModel):
    name: str
    issuer: str | None = None
    issued_year: int | None = None
    credential_id: str | None = None


class Achievements(BaseModel):
    """Categorized rather than one flat list.

    Note for the AI team: these are prose. They make good node *properties* but
    will not produce graph edges without entity extraction on their side.
    """

    career_highlights: list[str] = Field(default_factory=list)
    academic_distinctions: list[str] = Field(default_factory=list)
    awards_and_competitions: list[str] = Field(default_factory=list)
    projects_and_open_source: list[str] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return not any(
            (
                self.career_highlights,
                self.academic_distinctions,
                self.awards_and_competitions,
                self.projects_and_open_source,
            )
        )


class Links(BaseModel):
    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None


class AIMetadata(BaseModel):
    """Reserved for the AI team. The web application never writes this."""

    embedding_version: str | None = None
    last_parsed_at: datetime | None = None
    parsed_resume_id: PydanticObjectId | None = None


class CandidateProfile(Document):
    """1:1 with a candidate User.

    `experience` / `education` are embedded rather than referenced: they are
    bounded in size, always read alongside the profile, and never queried
    independently — the textbook case for embedding in MongoDB.
    """

    user_id: PydanticObjectId

    headline: str | None = None
    summary: str | None = None
    job_category: str | None = None
    seniority: SeniorityLevel | None = None

    location: Location = Field(default_factory=Location)
    open_to_relocate: bool = False
    work_modes: list[WorkMode] = Field(default_factory=list)

    # Normalized to lowercase on write so matching never depends on casing.
    skills: list[str] = Field(default_factory=list)
    years_experience: float | None = None
    expected_salary: SalaryExpectation | None = None

    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    achievements: Achievements = Field(default_factory=Achievements)
    links: Links = Field(default_factory=Links)

    primary_resume_id: PydanticObjectId | None = None
    saved_job_ids: list[PydanticObjectId] = Field(default_factory=list)

    completion_percent: int = 0

    ai: AIMetadata = Field(default_factory=AIMetadata)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def recompute_completion(self) -> int:
        """Drives the 'complete your profile' nudge on the candidate dashboard."""
        checks = [
            bool(self.headline),
            bool(self.summary),
            bool(self.job_category),
            self.seniority is not None,
            bool(self.location.country),
            len(self.skills) >= 3,
            bool(self.experience),
            bool(self.education),
            self.primary_resume_id is not None,
            self.years_experience is not None,
        ]
        self.completion_percent = round(sum(checks) / len(checks) * 100)
        return self.completion_percent

    class Settings:
        name = "candidate_profiles"
        indexes = [
            IndexModel([("user_id", ASCENDING)], unique=True, name="uniq_user"),
            IndexModel([("skills", ASCENDING)], name="skills_multikey"),
            IndexModel(
                [("job_category", ASCENDING), ("seniority", ASCENDING)],
                name="category_seniority",
            ),
            IndexModel(
                [("headline", TEXT), ("summary", TEXT), ("skills", TEXT)],
                name="profile_text",
            ),
        ]
